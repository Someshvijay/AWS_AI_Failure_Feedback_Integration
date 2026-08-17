import TodoItem from "./TodoItem";

function TodoList({ todos, onDelete }) {
  if (!todos.length) {
    return <p>No tasks available.</p>;
  }

  return (
    <ul className="todo-list">
      {todos.map((todo) => (
        <TodoItem
          key={todo.id}
          todo={todo}
          onDelete={onDelete}
        />
      ))}
    </ul>
  );
}

export default TodoList;