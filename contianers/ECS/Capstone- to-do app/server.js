// Simple To-Do list API + static frontend.
// Storage: DynamoDB.
//
// Two modes, chosen by one environment variable:
//   DDB_ENDPOINT set    -> DynamoDB Local (the "database" container)
//   DDB_ENDPOINT unset  -> the real, managed Amazon DynamoDB service

const express = require('express');
const path = require('path');
const { randomUUID } = require('crypto');

const {
  DynamoDBClient,
  CreateTableCommand,
  DescribeTableCommand,
  waitUntilTableExists
} = require('@aws-sdk/client-dynamodb');

const {
  DynamoDBDocumentClient,
  ScanCommand,
  GetCommand,
  PutCommand,
  UpdateCommand,
  DeleteCommand
} = require('@aws-sdk/lib-dynamodb');

const app = express();
const PORT = process.env.PORT || 3000;

// "Due soon / overdue" window, in days.
const OVERDUE_DAYS = 3;

const TABLE = process.env.DDB_TABLE || 'Tasks';
const ENDPOINT = process.env.DDB_ENDPOINT || '';
const REGION = process.env.AWS_REGION || 'ap-south-1';

const config = { region: REGION };
if (ENDPOINT) {
  config.endpoint = ENDPOINT;
  // DynamoDB Local ignores credentials entirely, but the SDK still refuses to
  // send a request without finding some, so give it throwaway values.
  config.credentials = { accessKeyId: 'local', secretAccessKey: 'local' };
}

// The low-level client is used for table admin (create / describe).
const client = new DynamoDBClient(config);

// The document client is used for everything else. It converts plain JavaScript
// objects to and from DynamoDB's typed format, so the code never has to write
// { "title": { "S": "..." } } by hand.
const ddb = DynamoDBDocumentClient.from(client, {
  marshallOptions: { removeUndefinedValues: true }
});

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

/* ---------------------------------------------------------------
   Table
   --------------------------------------------------------------- */

// DynamoDB is schemaless: only the key has to be declared. Every other
// attribute (title, description, dueDate, status, createdAt) is just written
// with the item, which is why there is no CREATE TABLE column list here.
async function createTable() {
  try {
    await client.send(new DescribeTableCommand({ TableName: TABLE }));
    return; // already there
  } catch (err) {
    if (err.name !== 'ResourceNotFoundException') throw err;
  }

  console.log(`Creating table "${TABLE}"...`);
  await client.send(new CreateTableCommand({
    TableName: TABLE,
    AttributeDefinitions: [{ AttributeName: 'id', AttributeType: 'S' }],
    KeySchema: [{ AttributeName: 'id', KeyType: 'HASH' }],
    // On-demand: no capacity to size, and nothing to pay when it is idle.
    BillingMode: 'PAY_PER_REQUEST'
  }));

  await waitUntilTableExists({ client, maxWaitTime: 120 }, { TableName: TABLE });
}

// "status" is a reserved word in DynamoDB expressions, so it can never appear
// directly - it always has to go through a #placeholder name.
const STATUS_NAME = { '#status': 'status' };

/* ---------------------------------------------------------------
   Helpers
   --------------------------------------------------------------- */

// Whole days from today until the due date. Negative = already past.
function daysUntil(dueDate) {
  if (!dueDate) return null;
  const due = new Date(dueDate + 'T00:00:00');
  if (isNaN(due.getTime())) return null;

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return Math.round((due - today) / (1000 * 60 * 60 * 24));
}

// Adds the fields the UI needs but that we do not store in the table.
function decorate(task) {
  const days = daysUntil(task.dueDate);
  const open = task.status !== 'completed';

  return {
    ...task,
    daysLeft: days,
    // Past the due date and still not done.
    isOverdue: open && days !== null && days < 0,
    // Due within the next OVERDUE_DAYS days.
    isDueSoon: open && days !== null && days >= 0 && days <= OVERDUE_DAYS
  };
}

function isValidDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !isNaN(new Date(value).getTime());
}

// Express 4 does not catch errors thrown inside an async route, so every route
// is wrapped in this helper to turn a failed call into a clean 500.
function wrap(handler) {
  return (req, res) => {
    handler(req, res).catch((err) => {
      console.error(err);
      res.status(500).json({ error: 'Database error' });
    });
  };
}

async function getTask(id) {
  const { Item } = await ddb.send(new GetCommand({ TableName: TABLE, Key: { id } }));
  return Item;
}

/* ---------------------------------------------------------------
   API routes
   --------------------------------------------------------------- */

// GET /api/tasks              -> all tasks
// GET /api/tasks?status=pending | completed
app.get('/api/tasks', wrap(async (req, res) => {
  // Scan reads the whole table. That is the right call for a to-do list of a
  // few hundred items; a real high-volume table would use a Query against an
  // index instead.
  const params = { TableName: TABLE };

  const status = req.query.status;
  if (status === 'pending' || status === 'completed') {
    params.FilterExpression = '#status = :status';
    params.ExpressionAttributeNames = STATUS_NAME;
    params.ExpressionAttributeValues = { ':status': status };
  }

  const { Items = [] } = await ddb.send(new ScanCommand(params));

  // DynamoDB returns items in no particular order, so sort them here.
  Items.sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt)));

  res.json(Items.map(decorate));
}));

// GET /api/tasks/:id -> one task
app.get('/api/tasks/:id', wrap(async (req, res) => {
  const task = await getTask(req.params.id);
  if (!task) return res.status(404).json({ error: 'Task not found' });

  res.json(decorate(task));
}));

// POST /api/tasks -> create a task (always starts as "pending")
app.post('/api/tasks', wrap(async (req, res) => {
  const { title, description, dueDate } = req.body || {};

  if (!title || !String(title).trim()) {
    return res.status(400).json({ error: 'Title is required' });
  }
  if (!dueDate || !isValidDate(dueDate)) {
    return res.status(400).json({ error: 'Due date is required (YYYY-MM-DD)' });
  }

  // DynamoDB has no auto-increment, so the app generates the key itself.
  const task = {
    id: randomUUID(),
    title: String(title).trim(),
    description: description ? String(description).trim() : '',
    dueDate: dueDate,
    status: 'pending',
    createdAt: new Date().toISOString()
  };

  await ddb.send(new PutCommand({ TableName: TABLE, Item: task }));

  res.status(201).json(decorate(task));
}));

// PUT /api/tasks/:id -> edit a task (title / description / dueDate / status)
app.put('/api/tasks/:id', wrap(async (req, res) => {
  const task = await getTask(req.params.id);
  if (!task) return res.status(404).json({ error: 'Task not found' });

  const { title, description, dueDate, status } = req.body || {};

  if (title !== undefined) {
    if (!String(title).trim()) {
      return res.status(400).json({ error: 'Title cannot be empty' });
    }
    task.title = String(title).trim();
  }

  if (description !== undefined) {
    task.description = description ? String(description).trim() : '';
  }

  if (dueDate !== undefined) {
    if (!isValidDate(dueDate)) {
      return res.status(400).json({ error: 'Due date must be YYYY-MM-DD' });
    }
    task.dueDate = dueDate;
  }

  if (status !== undefined) {
    if (status !== 'pending' && status !== 'completed') {
      return res.status(400).json({ error: 'Status must be "pending" or "completed"' });
    }
    task.status = status;
  }

  // Put replaces the whole item, which is what we want here: the object above
  // is the complete task, just with the edited fields changed.
  await ddb.send(new PutCommand({ TableName: TABLE, Item: task }));

  res.json(decorate(task));
}));

// PATCH /api/tasks/:id/toggle -> flip pending <-> completed (the checkbox)
app.patch('/api/tasks/:id/toggle', wrap(async (req, res) => {
  const task = await getTask(req.params.id);
  if (!task) return res.status(404).json({ error: 'Task not found' });

  const next = task.status === 'completed' ? 'pending' : 'completed';

  // Update changes one attribute in place instead of rewriting the item.
  const { Attributes } = await ddb.send(new UpdateCommand({
    TableName: TABLE,
    Key: { id: req.params.id },
    UpdateExpression: 'SET #status = :status',
    ExpressionAttributeNames: STATUS_NAME,
    ExpressionAttributeValues: { ':status': next },
    ReturnValues: 'ALL_NEW'
  }));

  res.json(decorate(Attributes));
}));

// DELETE /api/tasks/:id -> remove a task
app.delete('/api/tasks/:id', wrap(async (req, res) => {
  // ALL_OLD hands back what was deleted, which also tells us whether the item
  // existed at all - a delete of a missing key is not an error in DynamoDB.
  const { Attributes } = await ddb.send(new DeleteCommand({
    TableName: TABLE,
    Key: { id: req.params.id },
    ReturnValues: 'ALL_OLD'
  }));

  if (!Attributes) return res.status(404).json({ error: 'Task not found' });

  res.json({ message: 'Task deleted', task: Attributes });
}));

/* ---------------------------------------------------------------
   Start
   --------------------------------------------------------------- */

async function start() {
  // The DynamoDB Local container is usually still starting up when this one
  // boots, so keep retrying for about a minute before giving up.
  for (let attempt = 1; ; attempt++) {
    try {
      await createTable();
      break;
    } catch (err) {
      if (attempt >= 30) throw err;
      console.log(`Waiting for DynamoDB (attempt ${attempt})...`);
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }

  console.log(`Using table "${TABLE}" on ${ENDPOINT || `managed DynamoDB in ${REGION}`}`);

  app.listen(PORT, () => {
    console.log(`To-Do app running at http://localhost:${PORT}`);
  });
}

start().catch((err) => {
  console.error('Could not start the app:', err.message);
  process.exit(1);
});
