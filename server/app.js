const express = require("express");
const cors = require("cors");
const pool = require("./db/database");

const app = express();

app.use(cors({
  origin: [
    'http://localhost:5173',
    /\.app\.github\.dev$/,
    'http://13.207.171.80'
  ]
}));
app.use(express.json());

/*
  GET ALL TASKS
*/
app.get("/api/todos", async (req, res) => {
  try {
    const result = await pool.query("SELECT * FROM tasks ORDER BY id ASC");
    res.status(200).json(result.rows);
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Failed to fetch tasks" });
  }
});

/*
  GET TASK BY ID
*/
app.get("/api/todos/:id", async (req, res) => {
  try {
    const result = await pool.query("SELECT * FROM tasks WHERE id = $1", [
      req.params.id,
    ]);

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Task not found" });
    }

    res.json(result.rows[0]);
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Failed to fetch task" });
  }
});

/*
  CREATE TASK
*/
app.post("/api/todos", async (req, res) => {
  try {
    const { text, date, timeOfDay, isImportant } = req.body;

    if (!text || !text.trim()) {
      return res.status(400).json({ message: "Task title is required" });
    }

    const result = await pool.query(
      `
      INSERT INTO tasks(title, due_date, time_of_day, is_important)
      VALUES($1, $2, $3, $4)
      RETURNING *
      `,
      [text, date || null, timeOfDay || "day", isImportant || false],
    );

    res.status(201).json(result.rows[0]);
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Failed to create task" });
  }
});

/*
  UPDATE TASK
*/
app.put("/api/todos/:id", async (req, res) => {
  try {
    const { title, completed, date, timeOfDay, isImportant } = req.body;

    const result = await pool.query(
      `
      UPDATE tasks
      SET
        title = COALESCE($1, title),
        completed = COALESCE($2, completed),
        due_date = COALESCE($3, due_date),
        time_of_day = COALESCE($4, time_of_day),
        is_important = COALESCE($5, is_important)
      WHERE id = $6
      RETURNING *
      `,
      [title, completed, date, timeOfDay, isImportant, req.params.id],
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Task not found" });
    }

    res.json(result.rows[0]);
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Failed to update task" });
  }
});

/*
  MARK TASK COMPLETE
*/
/*
  TOGGLE TASK COMPLETE
*/
app.patch("/api/todos/:id/complete", async (req, res) => {
  try {
    const result = await pool.query(
      `
      UPDATE tasks
      SET completed = NOT completed
      WHERE id = $1
      RETURNING id, title, completed, time_of_day, is_important,
                TO_CHAR(due_date, 'YYYY-MM-DD') AS due_date
      `,
      [req.params.id],
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Task not found" });
    }

    res.json(result.rows[0]);
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Failed to toggle task" });
  }
});

/*
  DELETE TASK
*/
app.delete("/api/todos/:id", async (req, res) => {
  try {
    const result = await pool.query(
      "DELETE FROM tasks WHERE id = $1 RETURNING *",
      [req.params.id],
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ message: "Task not found" });
    }

    res.json({ message: "Task deleted successfully" });
  } catch (error) {
    console.error(error);
    res.status(500).json({ message: "Failed to delete task" });
  }
});

module.exports = app;