import * as React from "react";
import { CalendarDays } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type DatePickerProps = {
  className?: string;
  placeholder?: string;
  value?: string;
  onChange: (value: string) => void;
};

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function parseDate(value?: string) {
  if (!value) return undefined;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return undefined;
  const date = new Date(year, month - 1, day);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

function formatDate(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function displayDate(value?: string, placeholder = "选择日期") {
  const date = parseDate(value);
  if (!date) return placeholder;
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())}`;
}

function DatePicker({ className, placeholder, value, onChange }: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  const selected = React.useMemo(() => parseDate(value), [value]);

  function selectDay(day?: Date) {
    if (!day) return;
    onChange(formatDate(day));
    setOpen(false);
  }

  function useToday() {
    onChange(formatDate(new Date()));
    setOpen(false);
  }

  function clear() {
    onChange("");
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          data-slot="date-picker-trigger"
          variant="outline"
          className={cn("sj-date-picker-trigger", className)}
        >
          <span>{displayDate(value, placeholder)}</span>
          <CalendarDays data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent data-slot="date-picker-content" align="start" className="sj-date-picker-content">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={selectDay}
          weekStartsOn={1}
          formatters={{
            formatCaption: (date) => `${date.getFullYear()}年${pad(date.getMonth() + 1)}月`,
            formatWeekdayName: (date) => WEEKDAYS[date.getDay()]
          }}
        />
        <div className="sj-date-picker-actions">
          <Button type="button" variant="ghost" size="sm" onClick={clear}>清除</Button>
          <Button type="button" variant="outline" size="sm" onClick={useToday}>今天</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export { DatePicker };
