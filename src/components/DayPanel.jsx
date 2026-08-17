import PropTypes from "prop-types";
import { useState } from "react";

function TaskRow({ todo, onUpdate, onToggle, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(todo.title);

  if (editing) {
    return (
      <li className="p5-task editing">
        <input value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
        <div className="p5-task-actions">
          <button
            onClick={() => {
              onUpdate(todo.id, { title: draft });
              setEditing(false);
            }}
          >
            ✓
          </button>
          <button onClick={() => setEditing(false)}>✕</button>
        </div>
      </li>
    );
  }

  return (
    <li className={`p5-task${todo.completed ? " done" : ""}`}>
      <label className="p5-check">
        <input type="checkbox" checked={todo.completed} onChange={() => onToggle(todo.id)} />
        <span className="p5-task-title">
          {todo.is_important && <b className="p5-bang">!</b>}
          {todo.title}
        </span>
      </label>

      <div className="p5-task-actions">
        <button
          onClick={() => onUpdate(todo.id, { isImportant: !todo.is_important })}
          title="Toggle important"
        >
          ★
        </button>
        <button onClick={() => setEditing(true)}>Edit</button>
        <button onClick={() => onDelete(todo.id)}>Del</button>
      </div>
    </li>
  );
}

TaskRow.propTypes = {
  todo: PropTypes.object.isRequired,
  onUpdate: PropTypes.func.isRequired,
  onToggle: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};

function DayPanel({ selectedDate, todos, onAdd, onUpdate, onToggle, onDelete }) {
  const [text, setText] = useState("");
  const [slot, setSlot] = useState("day");
  const [important, setImportant] = useState(false);

  const dayTodos = todos.filter(
    (t) => t.due_date && t.due_date.split("T")[0] === selectedDate
  );

  const submit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onAdd(text, selectedDate, slot, important);
    setText("");
    setImportant(false);
  };

  const label = selectedDate
    ? (() => {
        const d = new Date(selectedDate + "T00:00:00");
        const wd = d.toLocaleDateString("default", { weekday: "short" });
        return `${d.getMonth() + 1}/${d.getDate()} (${wd})`;
      })()
    : "";

  const section = (title, slotKey) => {
    const list = dayTodos.filter((t) => (t.time_of_day || "day") === slotKey);
    return (
      <div className="p5-section">
        <h3 className="p5-section-title">{title}</h3>
        <ul className="p5-task-list">
          {list.length === 0 && <p className="p5-empty">—</p>}
          {list.map((t) => (
            <TaskRow
              key={t.id}
              todo={t}
              onUpdate={onUpdate}
              onToggle={onToggle}
              onDelete={onDelete}
            />
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="p5-panel">
      <div className="p5-date-tag">{label}</div>

      <form onSubmit={submit} className="p5-add-form">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="ADD TASK..."
        />
        <select value={slot} onChange={(e) => setSlot(e.target.value)}>
          <option value="day">DAY</option>
          <option value="night">NIGHT</option>
        </select>
        <label className="p5-imp-toggle">
          <input
            type="checkbox"
            checked={important}
            onChange={(e) => setImportant(e.target.checked)}
          />
          !
        </label>
        <button type="submit">+</button>
      </form>

      {section("Day", "day")}
      {section("Night", "night")}
    </div>
  );
}

DayPanel.propTypes = {
  selectedDate: PropTypes.string,
  todos: PropTypes.array.isRequired,
  onAdd: PropTypes.func.isRequired,
  onUpdate: PropTypes.func.isRequired,
  onToggle: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};

export default DayPanel;