import { useEffect, useState } from "react";
import './App.css';
import Calendar from "./components/Calendar";
import DayPanel from "./components/DayPanel";
import {
  getTodos,
  createTodo,
  updateTodo,
  toggleComplete,
  deleteTodo,
} from "./services/todoService";

function App() {
  const [todos, setTodos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split("T")[0]
  );

  useEffect(() => {
    loadTodos();
  }, []);

  const loadTodos = async () => {
    try {
      setTodos(await getTodos());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

const handleAdd = async (text, date, timeOfDay, isImportant) => {
    const newTodo = await createTodo(text, date, timeOfDay, isImportant);
    setTodos((prev) => [...prev, newTodo]);
  };

  const handleUpdate = async (id, updates) => {
    const updated = await updateTodo(id, updates);
    setTodos((prev) => prev.map((t) => (t.id === id ? updated : t)));
  };

  const handleToggle = async (id) => {
    const updated = await toggleComplete(id);
    setTodos((prev) => prev.map((t) => (t.id === id ? updated : t)));
  };

  const handleDelete = async (id) => {
    await deleteTodo(id);
    setTodos((prev) => prev.filter((t) => t.id !== id));
  };

  const changeMonth = (offset) =>
    setCurrentMonth((prev) => new Date(prev.getFullYear(), prev.getMonth() + offset, 1));

  if (loading) return <p className="p5-loading">Loading...</p>;

  return (
    <div className="p5-app">
      <Calendar
        currentMonth={currentMonth}
        selectedDate={selectedDate}
        onSelectDate={setSelectedDate}
        onMonthChange={changeMonth}
        todos={todos}
      />
      <DayPanel
        selectedDate={selectedDate}
        todos={todos}
        onAdd={handleAdd}
        onUpdate={handleUpdate}
        onToggle={handleToggle}
        onDelete={handleDelete}
      />
    </div>
  );
}

export default App;