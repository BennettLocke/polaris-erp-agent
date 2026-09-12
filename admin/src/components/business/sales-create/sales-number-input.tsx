import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { commitSalesNumberDraft, parseSalesNumberDraft } from "./sales-number-input-state";
import { inputNoWheel } from "./utils";

type SalesNumberInputProps = {
  value: number;
  minimum?: number;
  step?: number | "any";
  ariaLabel: string;
  onValueChange: (value: number) => void;
};

function SalesNumberInput({
  value,
  minimum = 1,
  step = "any",
  ariaLabel,
  onValueChange
}: SalesNumberInputProps) {
  const [draft, setDraft] = useState(String(value));
  const editing = useRef(false);

  useEffect(() => {
    if (!editing.current) setDraft(String(value));
  }, [value]);

  function finishEditing() {
    editing.current = false;
    const committed = commitSalesNumberDraft(draft, value, minimum);
    setDraft(String(committed));
    if (committed !== value) onValueChange(committed);
  }

  return (
    <Input
      aria-label={ariaLabel}
      type="number"
      inputMode="decimal"
      min={minimum}
      step={step}
      value={draft}
      onFocus={() => {
        editing.current = true;
      }}
      onWheel={inputNoWheel}
      onChange={(event) => {
        const nextDraft = event.target.value;
        setDraft(nextDraft);
        const nextValue = parseSalesNumberDraft(nextDraft, minimum);
        if (nextValue !== null) onValueChange(nextValue);
      }}
      onBlur={finishEditing}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

export { SalesNumberInput };
