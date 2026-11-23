import { useEffect, useMemo, useRef, useState } from "react";

interface Option {
  value: string;
  label: string;
}

export function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = "— Chọn —",
  required,
  id,
}: {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedLabel = options.find((o) => o.value === value)?.label ?? "";

  const filtered = useMemo(() => {
    if (!query.trim()) return options;
    const normalizedQuery = normalize(query);
    return options.filter((o) => normalize(o.label).includes(normalizedQuery));
  }, [options, query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="searchable-select" ref={containerRef}>
      <input
        id={id}
        type="text"
        value={open ? query : selectedLabel}
        placeholder={placeholder}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onChange={(e) => setQuery(e.target.value)}
        required={required && !value}
        autoComplete="off"
      />
      {open && (
        <div className="searchable-select__menu">
          {filtered.length === 0 ? (
            <div className="searchable-select__empty">Không tìm thấy — thử gõ tên khác</div>
          ) : (
            filtered.map((o) => (
              <div
                key={o.value}
                className="searchable-select__option"
                onMouseDown={() => {
                  onChange(o.value);
                  setOpen(false);
                  setQuery("");
                }}
              >
                {o.label}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d");
}
