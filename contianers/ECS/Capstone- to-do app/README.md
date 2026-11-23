# To-Do List Web Application

A simple to-do list app built with **Node.js + Express** and a plain **HTML/CSS/JavaScript** frontend.
Tasks are stored in **DynamoDB**, which runs as a second container (DynamoDB Local).
The app itself keeps no data on disk, so it can be restarted or replaced without
losing anything.

---

## 1. Project structure

```
to-do application/
├── server.js           # Express server + REST API
├── package.json        # Project info and dependencies
├── Dockerfile          # Container image definition
├── docker-compose.yml  # Runs both containers locally
├── .dockerignore
├── .gitignore
├── README.md           # This file
├── ecs/
│   ├── todo-fargate-efs.yaml   # ECS Fargate + EFS CloudFormation stack
│   └── README.md               # How to deploy it
└── public/             # Frontend served as static files
    ├── index.html      # Page structure
    ├── style.css       # Styling (brand colours, hover effects, states)
    ├── script.js       # Fetch calls + rendering + filters + cursor effects
    └── images/
        └── logo.png    # Aviz Academy logo (shown in the sticky header)
```

---

## 2. How to run the application

### Option A — Two containers with Docker Compose (recommended)

This is the same shape the app runs in on AWS: one container for the frontend,
one for the database.

```bash
docker compose up --build
```

Open <http://localhost:3000>.

Stop them with `docker compose down`. The tasks survive, because DynamoDB Local
keeps its database file in a Docker volume. Use `docker compose down -v` to wipe
that volume too.

### Option B — Run with Node.js directly

Requirements: Node.js 18 or newer, plus a DynamoDB you can reach.

```bash
docker run -d --name todo-db -p 8000:8000 amazon/dynamodb-local:latest -jar DynamoDBLocal.jar -sharedDb
```

```bash
npm install
DDB_ENDPOINT=http://localhost:8000 npm start
```

Configuration comes from environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `DDB_ENDPOINT` | *(unset)* | Set = DynamoDB Local at this URL. Unset = the real DynamoDB service. |
| `DDB_TABLE` | `Tasks` | Table name |
| `AWS_REGION` | `ap-south-1` | Region |
| `PORT` | `3000` | Web port |

The table is created automatically on startup, so there is no setup step to run.

To use the **real** DynamoDB service instead, leave `DDB_ENDPOINT` unset and make
sure your AWS credentials are available:

```bash
npm start
```

### Option C — On AWS ECS Fargate with EFS

See [ecs/README.md](ecs/README.md).

---

## 3. Features

| Requirement | How it works |
|---|---|
| Create / edit / delete tasks | Form at the top of the page; **Edit** loads a task into the form, **Delete** removes it |
| Task fields | Title (required), Description (optional), Due date (required), Status |
| Default status | Every new task is saved as `pending` |
| Checkbox completes a task | Clicking the checkbox calls `PATCH /api/tasks/:id/toggle` |
| Completed tasks look different | Green background, strike-through title, faded, and sorted below pending tasks |
| Bring a task back to pending | Un-tick the same checkbox — the toggle works both ways |
| Filters | **All / Pending / Completed** buttons above the list, each with a live count |
| Overdue highlight | See below |

### Look and feel

- The **Aviz Academy logo** and the subtitle *"Aviz Academy &ndash; Batch 10 Docker Demo"* sit in a
  sticky header, so they stay visible while you scroll.
- Colours are taken from the logo: navy blue, orange and sky blue.
- Hover effects that respond to the pointer:
  - a soft halo follows the mouse around the page;
  - cards and task rows show a spotlight that tracks the cursor, and lift slightly;
  - the **Add task** button has a light sweep, and Edit/Delete fade in on the row you point at;
  - the logo, checkboxes and filter buttons all react on hover.
- Task rows fade in one after another, and a newly added or edited task pulses once.
- Everything is plain CSS and vanilla JavaScript &mdash; no frameworks or build step.
- Animations are switched off automatically for users who set *reduce motion* in their OS.

### Overdue and due-soon highlighting

The app uses a **3-day window**:

- **Red** — the due date has already passed and the task is still pending (badge: *Overdue by N days*).
- **Amber** — the task is due today or within the next **3 days** (badge: *Due today* / *Due in N days*).
- **Blue** — pending, more than 3 days away.
- **Green** — completed (no overdue highlight, since it is already done).

The window is set by the `OVERDUE_DAYS` constant near the top of `server.js`.

---

## 4. Task format

The API returns each task like this:

```json
{
  "id": "8c4132c7-d026-4056-9a28-0849209c7a54",
  "title": "Submit project report",
  "description": "Final version of the batch 10 project report",
  "dueDate": "2026-08-30",
  "status": "pending",
  "createdAt": "2026-08-25T09:00:00.000Z"
}
```

`status` is either `"pending"` or `"completed"`. `dueDate` uses the `YYYY-MM-DD` format.

That whole object is one DynamoDB item. The table declares only the key —
`id`, a string partition key — because DynamoDB is schemaless and every other
attribute is simply written with the item. `id` is a UUID generated by the app,
since DynamoDB has no auto-increment.

API responses add three calculated fields that are **not** stored in the database:
`daysLeft`, `isOverdue`, `isDueSoon`.

Two DynamoDB details worth knowing when reading `server.js`: `status` is a
**reserved word**, so it can only appear in an expression through a `#status`
placeholder; and listing tasks uses `Scan`, which reads the whole table — fine
for a to-do list, wrong for a large one.

The page loads every task with one `GET /api/tasks` call and then filters in the browser,
so the counts on the filter buttons always show the totals. The `?status=` query below is
still available for API users.

---

## 5. API endpoints

Base URL: `http://localhost:3000`

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/tasks` | List all tasks |
| `GET` | `/api/tasks?status=pending` | List pending tasks only |
| `GET` | `/api/tasks?status=completed` | List completed tasks only |
| `GET` | `/api/tasks/:id` | Get one task |
| `POST` | `/api/tasks` | Create a task (always starts as `pending`) |
| `PUT` | `/api/tasks/:id` | Update title / description / dueDate / status |
| `PATCH` | `/api/tasks/:id/toggle` | Complete a task, or move it back to pending |
| `DELETE` | `/api/tasks/:id` | Delete a task |

### Examples

**Create a task**

```bash
curl -X POST http://localhost:3000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy groceries","description":"Milk and rice","dueDate":"2026-09-10"}'
```

**Update a task**

```bash
curl -X PUT http://localhost:3000/api/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"title":"Submit final report","dueDate":"2026-09-15"}'
```

**Complete a task (or send it back to pending)**

```bash
curl -X PATCH http://localhost:3000/api/tasks/1/toggle
```

**Delete a task**

```bash
curl -X DELETE http://localhost:3000/api/tasks/1
```

### Error responses

| Status | When |
|---|---|
| `400` | Missing title, missing/invalid due date, or an invalid status value |
| `404` | No task exists with the given id |
