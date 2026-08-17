import PropTypes from "prop-types";


function Calendar({ currentMonth, selectedDate, onSelectDate, onMonthChange, todos }) {
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const pad = (n) => String(n).padStart(2, "0");
  const todayStr = (() => {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  })();

  const byDate = {};
  todos.forEach((t) => {
    if (!t.due_date) return;
    const key = t.due_date.split("T")[0];
    (byDate[key] = byDate[key] || []).push(t);
  });

  const cells = [];
  for (let i = 0; i < firstDay; i++) {
    cells.push(<div className="p5-num empty" key={`e-${i}`} />);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${pad(month + 1)}-${pad(day)}`;
    const weekday = new Date(year, month, day).getDay();
    const dayTasks = byDate[dateStr] || [];

    const isPast = dateStr < todayStr;
    const isToday = dateStr === todayStr;
    const isSelected = dateStr === selectedDate;
    const hasDay = dayTasks.some((t) => t.time_of_day === "day" && !t.completed);
    const hasNight = dayTasks.some((t) => t.time_of_day === "night" && !t.completed);
    const hasImportant = dayTasks.some((t) => t.is_important && !t.completed);
    const allDone = dayTasks.length > 0 && dayTasks.every((t) => t.completed);

    const classes = [
      "p5-num",
      weekday === 0 ? "sun" : "",
      weekday === 6 ? "sat" : "",
      isPast ? "past" : "",
      isToday ? "today" : "",
      isSelected ? "selected" : "",
      hasImportant ? "important" : "",
      allDone ? "all-done" : "",
    ]
      .filter(Boolean)
      .join(" ");

    cells.push(
      <div key={dateStr} className={classes} onClick={() => onSelectDate(dateStr)}>
        <span className="p5-num-text">{day}</span>

        {(hasDay || hasNight) && (
          <span className="p5-marks">
            {hasDay && <i className="mark-day" />}
            {hasNight && <i className="mark-night" />}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="p5-calendar">
      <div className="p5-cal-header">
        <button onClick={() => onMonthChange(-1)}>◄</button>
        <h2>{currentMonth.toLocaleString("default", { month: "long" }).toUpperCase()}</h2>
        <button onClick={() => onMonthChange(1)}>►</button>
      </div>

      <div className="p5-weekdays">
        {["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].map((d, i) => (
          <div key={d} className={`p5-weekday${i === 0 ? " sun" : ""}${i === 6 ? " sat" : ""}`}>
            {d}
          </div>
        ))}
      </div>

      <div className="p5-days">{cells}</div>

    </div>
  );
}

Calendar.propTypes = {
  currentMonth: PropTypes.instanceOf(Date).isRequired,
  selectedDate: PropTypes.string,
  onSelectDate: PropTypes.func.isRequired,
  onMonthChange: PropTypes.func.isRequired,
  todos: PropTypes.array.isRequired,
};

export default Calendar;