function TodoItem({ todo, onDelete }) {
  return (
    <li className="todo-item">
      <span>{todo.title}</span>

      <button
        onClick={() => onDelete(todo.id)}
        className="delete-btn"
      >
        Delete
      </button>
    </li>
  );
}

export default TodoItem;
