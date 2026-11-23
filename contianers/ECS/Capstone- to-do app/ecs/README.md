# Running the To-Do app on ECS Fargate with DynamoDB and EFS

A POC for class. Two containers, one task, one file system.

```
                      ECS Fargate task (awsvpc)
        ┌──────────────────────────────────────────────┐
        │                                              │
 :3000 ─┤  frontend            database                │
        │  (Node.js)  ──────>  (DynamoDB Local)        │
        │             localhost:8000    │              │
        └───────────────────────────────┼──────────────┘
                                        │ NFS :2049
                                   ┌────┴────┐
                                   │   EFS   │  /ddbdata
                                   └─────────┘
```

Both containers sit in the **same task**, so they share one network namespace.
That is why the app connects to `localhost:8000` — no service discovery, no
load balancer, nothing extra to explain.

## Why EFS is here at all

DynamoDB Local keeps its entire dataset in **one SQLite file**. Fargate gives a
task no disk you can keep, so without EFS every task replacement would start
from an empty table. Mounting EFS at the container's data directory is what
makes the tasks outlive the container.

Note that this is the one arrangement where EFS and DynamoDB make sense
together. If you move to the **managed** DynamoDB service (see the last section),
AWS stores the data for you, the database container disappears, and there is
nothing left for EFS to hold.

## What the template creates

| Resource | Why |
|---|---|
| EFS file system + 2 mount targets | Where the DynamoDB Local `.db` file lives |
| EFS access point | Pins the directory to `/ddbdata` and the POSIX user to uid 1000 |
| 2 security groups | Port 3000 open to the world; port 2049 open only to the task |
| ECS cluster, task definition, service | The two containers |
| CloudWatch log group | `/ecs/todo-ecs-poc`, 7 day retention |
| Task execution role | Lets the ECS agent pull from ECR and write logs |

Port 8000 is never opened in a security group. DynamoDB Local is reachable only
from inside the task.

## Deploy

Set your values once:

```bash
export REGION=ap-south-1 ACCOUNT=111122223333 VPC=vpc-xxxxxxxx SUBNETS=subnet-aaaa,subnet-bbbb
```

The two subnets must be **public** and in **two different AZs**.

**1. Create the ECR repository**

```bash
aws ecr create-repository --repository-name todo-app --region $REGION
```

**2. Build and push the frontend image**

Fargate runs on x86 by default, so build for `linux/amd64` even from an M-series Mac:

```bash
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com
```

```bash
docker buildx build --platform linux/amd64 --push -t $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/todo-app:latest .
```

**3. Deploy the stack**

```bash
aws cloudformation deploy --region $REGION --stack-name todo-ecs-poc --template-file ecs/todo-fargate-efs.yaml --capabilities CAPABILITY_IAM --parameter-overrides ImageUri=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/todo-app:latest VpcId=$VPC SubnetIds=$SUBNETS
```

The `Tasks` table is created by the app on first start, so there is no separate
setup step.

**4. Find the URL**

```bash
aws ecs describe-tasks --region $REGION --cluster todo-ecs-poc-cluster --tasks $(aws ecs list-tasks --region $REGION --cluster todo-ecs-poc-cluster --query 'taskArns[0]' --output text) --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text | xargs -I {} aws ec2 describe-network-interfaces --region $REGION --network-interface-ids {} --query 'NetworkInterfaces[0].Association.PublicIp' --output text
```

Then browse to `http://<that-ip>:3000`.

## After a code change

Push a new image, then force the service to pick it up:

```bash
docker buildx build --platform linux/amd64 --push -t $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/todo-app:latest .
```

```bash
aws ecs update-service --region $REGION --cluster todo-ecs-poc-cluster --service todo-ecs-poc-service --force-new-deployment
```

The task gets a **new public IP** each time it is replaced. Put an ALB in front
if you want a stable address.

## Logs

```bash
aws logs tail /ecs/todo-ecs-poc --region $REGION --follow
```

## Tear it down

```bash
aws cloudformation delete-stack --region $REGION --stack-name todo-ecs-poc
```

This deletes the EFS file system and every task in it. The ECR repository is
not part of the stack, so remove it separately:

```bash
aws ecr delete-repository --region $REGION --repository-name todo-app --force
```

## Three things that will bite you

**The UID has to match.** An EFS access point squashes every file operation to
one POSIX user. The template uses **uid 1000**, which is `dynamodblocal` inside
the DynamoDB Local image. Get it wrong and the container starts, then loops on
`unable to open database file`.

**The image defaults to `-inMemory`.** That flag throws the data away when the
container stops, which would make the EFS volume completely pointless — the
symptom is an empty task list after every deploy, with no error anywhere. The
template overrides the command with `-sharedDb -dbPath /home/dynamodblocal/data`.
`-sharedDb` matters too: without it DynamoDB Local derives the file name from the
caller's access key and region, so a change in either silently opens a different,
empty database.

**Only one container may write the file.** That is why the service uses
`MaximumPercent: 100` / `MinimumHealthyPercent: 0` — the old task is stopped
*before* the replacement starts. It means a few seconds of downtime on every
deploy, and it is also why `DesiredCount` stays at 1.

## Switching to the managed DynamoDB service

The application code already supports this — it is one environment variable.
Everything else is infrastructure you remove.

1. **Delete `DDB_ENDPOINT`** from the frontend container's `Environment`. With
   no endpoint the SDK talks to the real service and picks up credentials from
   the task role.
2. **Delete** the `database` container, the `Volumes` block, the EFS file
   system, both mount targets, the access point, and `EfsSecurityGroup`.
3. **Add a task role**, because now IAM actually applies:

```yaml
  TaskRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: tasks-table-access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - dynamodb:CreateTable
                  - dynamodb:DescribeTable
                  - dynamodb:GetItem
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                  - dynamodb:DeleteItem
                  - dynamodb:Scan
                Resource: !Sub 'arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${TableName}'
```

   then reference it from the task definition:

```yaml
      TaskRoleArn: !GetAtt TaskRole.Arn
```

That version is closer to what you would actually run: no database container to
babysit, no single-writer restriction, so `DesiredCount` can go above 1 and the
deployment can be a normal rolling one.

## What this POC deliberately skips

An ALB in front, private subnets, and a `Query`-against-an-index access pattern
instead of `Scan`. `Scan` reads the whole table, which is exactly right for a
to-do list of a few hundred items and exactly wrong at scale.
