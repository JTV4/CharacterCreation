export default function SectionCollapse({
  title,
  open,
  onToggle,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className="section-collapse"
      aria-expanded={open}
      onClick={onToggle}
    >
      <span className={`section-chevron ${open ? "open" : ""}`}>&#9654;</span>
      {title}
    </button>
  );
}
