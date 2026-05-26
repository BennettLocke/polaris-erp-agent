import { createContext, useContext, useId, useMemo, useRef, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type ComboboxContextValue<T> = {
  activeIndex: number;
  filteredItems: T[];
  inputValue: string;
  itemToStringValue: (item: T) => string;
  listboxId: string;
  open: boolean;
  selectOnEnter: boolean;
  selectedValue: T | null;
  selectItem: (item: T) => void;
  setActiveIndex: (index: number) => void;
  setInputValue: (value: string) => void;
  setOpen: (open: boolean) => void;
};

const ComboboxContext = createContext<ComboboxContextValue<unknown> | null>(null);

function useComboboxContext<T>() {
  const context = useContext(ComboboxContext);
  if (!context) throw new Error("Combobox components must be used inside Combobox");
  return context as ComboboxContextValue<T>;
}

function Combobox<T>({
  children,
  className,
  filterItems = true,
  inputValue,
  itemToStringValue = (item) => String(item ?? ""),
  items,
  onInputValueChange,
  onValueChange,
  selectOnEnter = true,
  value = null
}: {
  children: ReactNode;
  className?: string;
  filterItems?: boolean;
  inputValue?: string;
  itemToStringValue?: (item: T) => string;
  items: T[];
  onInputValueChange?: (value: string) => void;
  onValueChange?: (value: T) => void;
  selectOnEnter?: boolean;
  value?: T | null;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [localInputValue, setLocalInputValue] = useState("");
  const currentInputValue = inputValue ?? localInputValue;
  const lowerQuery = currentInputValue.trim().toLowerCase();
  const filteredItems = useMemo(() => {
    if (!filterItems || !lowerQuery) return items;
    return items.filter((item) => itemToStringValue(item).toLowerCase().includes(lowerQuery));
  }, [filterItems, items, itemToStringValue, lowerQuery]);

  function updateInputValue(next: string) {
    setLocalInputValue(next);
    onInputValueChange?.(next);
  }

  function selectItem(item: T) {
    updateInputValue(itemToStringValue(item));
    onValueChange?.(item);
    setOpen(false);
  }

  return (
    <ComboboxContext.Provider
      value={{
        activeIndex,
        filteredItems,
        inputValue: currentInputValue,
        itemToStringValue,
        listboxId,
        open,
        selectOnEnter,
        selectedValue: value,
        selectItem,
        setActiveIndex,
        setInputValue: updateInputValue,
        setOpen
      } as ComboboxContextValue<unknown>}
    >
      <div
        data-slot="combobox"
        className={cn("sj-combobox", className)}
        ref={rootRef}
        onBlur={(event) => {
          const next = event.relatedTarget as Node | null;
          if (next && rootRef.current?.contains(next)) return;
          setOpen(false);
        }}
      >
        {children}
      </div>
    </ComboboxContext.Provider>
  );
}

function ComboboxInput({
  className,
  onChange,
  onFocus,
  onKeyDown,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  const {
    activeIndex,
    filteredItems,
    inputValue,
    listboxId,
    open,
    selectOnEnter,
    selectItem,
    setActiveIndex,
    setInputValue,
    setOpen
  } = useComboboxContext<unknown>();

  return (
    <input
      {...props}
      aria-autocomplete="list"
      aria-controls={listboxId}
      aria-expanded={open}
      className={cn("sj-input", className)}
      role="combobox"
      value={inputValue}
      onChange={(event) => {
        setInputValue(event.target.value);
        setActiveIndex(0);
        setOpen(true);
        onChange?.(event);
      }}
      onFocus={(event) => {
        setOpen(true);
        onFocus?.(event);
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setOpen(true);
          setActiveIndex(Math.min(filteredItems.length - 1, activeIndex + 1));
          return;
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          setActiveIndex(Math.max(0, activeIndex - 1));
          return;
        }
        if (event.key === "Escape") {
          setOpen(false);
          return;
        }
        if (event.key === "Enter" && selectOnEnter && open && filteredItems[activeIndex]) {
          event.preventDefault();
          selectItem(filteredItems[activeIndex]);
          return;
        }
        onKeyDown?.(event);
      }}
    />
  );
}

function ComboboxContent({ children }: { children: ReactNode }) {
  const { open } = useComboboxContext<unknown>();
  if (!open) return null;
  return <div className="sj-combobox-content">{children}</div>;
}

function ComboboxEmpty({ children }: { children: ReactNode }) {
  const { filteredItems } = useComboboxContext<unknown>();
  if (filteredItems.length) return null;
  return <div className="sj-combobox-empty">{children}</div>;
}

function ComboboxList<T>({ children }: { children: (item: T) => ReactNode }) {
  const { filteredItems, listboxId } = useComboboxContext<T>();
  if (!filteredItems.length) return null;
  return (
    <div className="sj-combobox-list" id={listboxId} role="listbox">
      {filteredItems.map((item) => children(item))}
    </div>
  );
}

function ComboboxItem<T>({ children, value }: { children: ReactNode; value: T }) {
  const { activeIndex, filteredItems, itemToStringValue, selectedValue, selectItem, setActiveIndex } = useComboboxContext<T>();
  const index = filteredItems.findIndex((item) => Object.is(item, value));
  const active = index === activeIndex;
  const selected = selectedValue ? itemToStringValue(selectedValue) === itemToStringValue(value) : false;
  return (
    <button
      className={cn("sj-combobox-item", (active || selected) && "active")}
      role="option"
      aria-selected={active || selected}
      type="button"
      onMouseDown={(event) => event.preventDefault()}
      onMouseEnter={() => setActiveIndex(Math.max(0, index))}
      onClick={() => selectItem(value)}
    >
      {children}
    </button>
  );
}

export {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
};
