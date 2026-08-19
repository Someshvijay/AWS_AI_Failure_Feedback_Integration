jest.mock("../db/database");

const request = require("supertest");
const app = require("../app");
const pool = require("../db/database");

beforeEach(() => {
  pool.query.mockReset();
});

describe("GET /api/todos", () => {
  test("returns 200 and a list of tasks", async () => {
    const mockTasks = [
      { id: 1, title: "Buy milk", completed: false },
      { id: 2, title: "Walk dog", completed: true },
    ];
    pool.query.mockResolvedValueOnce({ rows: mockTasks });

    const res = await request(app).get("/api/todos");

    expect(res.status).toBe(200);
    expect(res.body).toEqual(mockTasks);
  });

  test("returns 500 if the database query fails", async () => {
    pool.query.mockRejectedValueOnce(new Error("DB down"));

    const res = await request(app).get("/api/todos");

    expect(res.status).toBe(500);
    expect(res.body.message).toBe("Failed to fetch tasks");
  });
});

describe("GET /api/todos/:id", () => {
  test("returns 200 and the task when found", async () => {
    const mockTask = { id: 1, title: "Buy milk", completed: false };
    pool.query.mockResolvedValueOnce({ rows: [mockTask] });

    const res = await request(app).get("/api/todos/1");

    expect(res.status).toBe(200);
    expect(res.body).toEqual(mockTask);
  });

  test("returns 404 when the task doesn't exist", async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });

    const res = await request(app).get("/api/todos/999");

    expect(res.status).toBe(404);
    expect(res.body.message).toBe("Task not found");
  });
});

describe("POST /api/todos", () => {
  test("returns 201 and the created task", async () => {
    const newTask = { id: 3, title: "Read book", completed: false };
    pool.query.mockResolvedValueOnce({ rows: [newTask] });

    const res = await request(app)
      .post("/api/todos")
      .send({ text: "Read book" });

    expect(res.status).toBe(201);
    expect(res.body).toEqual(newTask);
  });

  test("returns 400 when text is missing", async () => {
    const res = await request(app).post("/api/todos").send({});

    expect(res.status).toBe(400);
    expect(res.body.message).toBe("Task title is required");
    expect(pool.query).not.toHaveBeenCalled();
  });

  test("returns 400 when text is empty/whitespace", async () => {
    const res = await request(app).post("/api/todos").send({ text: "   " });

    expect(res.status).toBe(400);
    expect(pool.query).not.toHaveBeenCalled();
  });
});

describe("PUT /api/todos/:id", () => {
  test("returns 200 and the updated task", async () => {
    const updatedTask = { id: 1, title: "Buy oat milk", completed: true };
    pool.query.mockResolvedValueOnce({ rows: [updatedTask] });

    const res = await request(app)
      .put("/api/todos/1")
      .send({ title: "Buy oat milk", completed: true });

    expect(res.status).toBe(999);
    expect(res.body).toEqual(updatedTask);
  });

  test("returns 404 when the task doesn't exist", async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });

    const res = await request(app)
      .put("/api/todos/999")
      .send({ title: "Doesn't matter" });

    expect(res.status).toBe(404);
  });
});

describe("PATCH /api/todos/:id/complete", () => {
  test("returns 200 and toggles completion", async () => {
    const completedTask = { id: 1, title: "Buy milk", completed: true };
    pool.query.mockResolvedValueOnce({ rows: [completedTask] });

    const res = await request(app).patch("/api/todos/1/complete");

    expect(res.status).toBe(200);
    expect(res.body.completed).toBe(true);
  });

  test("returns 404 when the task doesn't exist", async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });

    const res = await request(app).patch("/api/todos/999/complete");

    expect(res.status).toBe(404);
  });
});

describe("DELETE /api/todos/:id", () => {
  test("returns 200 and confirms deletion", async () => {
    pool.query.mockResolvedValueOnce({ rows: [{ id: 1 }] });

    const res = await request(app).delete("/api/todos/1");

    expect(res.status).toBe(200);
    expect(res.body.message).toBe("Task deleted successfully");
  });

  test("returns 404 when the task doesn't exist", async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });

    const res = await request(app).delete("/api/todos/999");

    expect(res.status).toBe(404);
  });
});