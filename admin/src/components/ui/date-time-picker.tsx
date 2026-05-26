import * as React from "react";
import { CalendarDays } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

type DateTimePickerProps = {
  className?: string;
  value?: string;
  onChange: (value: string) => void;
};

const HOURS = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const MINUTES = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, "0"));
const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function parseDateTime(value?: string) {
  if (!value) return new Date();
  const normalized = value.includes(" ") ? value.replace(" ", "T") : value;
  const [datePart, timePart = "00:00"] = normalized.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  const [hour, minute] = timePart.split(":").map(Number);
  const date = new Date(year, (month || 1) - 1, day || 1, hour || 0, minute || 0);
  return Number.isNaN(date.getTime()) ? new Date() : date;
}

function formatDateTime(date: Date) {
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate())
  ].join("-") + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function displayDateTime(value?: string) {
  if (!value) return "选择开单时间";
  const date = parseDateTime(value);
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function DateTimePicker({ className, value, onChange }: DateTimePickerProps) {
  const selected = React.useMemo(() => parseDateTime(value), [value]);

  function update(next: Date) {
    onChange(formatDateTime(next));
  }

  function changeDay(day?: Date) {
    if (!day) return;
    const next = new Date(day);
    next.setHours(selected.getHours(), selected.getMinutes(), 0, 0);
    update(next);
  }

  function changeTime(part: "hour" | "minute", nextValue: string) {
    const next = new Date(selected);
    if (part === "hour") next.setHours(Number(nextValue));
    if (part === "minute") next.setMinutes(Number(nextValue));
    next.setSeconds(0, 0);
    update(next);
  }

  function useNow() {
    const now = new Date();
    now.setSeconds(0, 0);
    update(now);
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          data-slot="date-time-picker-trigger"
          variant="outline"
          className={cn("sj-date-time-trigger", className)}
        >
          <span>{displayDateTime(value)}</span>
          <CalendarDays data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent data-slot="date-time-picker-content" align="start" className="sj-date-time-content">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={changeDay}
          weekStartsOn={1}
          formatters={{
            formatCaption: (date) => `${date.getFullYear()}年${pad(date.getMonth() + 1)}月`,
            formatWeekdayName: (date) => WEEKDAYS[date.getDay()]
          }}
        />
        <div className="sj-date-time-controls">
          <Select value={pad(selected.getHours())} onValueChange={(next) => changeTime("hour", next)}>
            <SelectTrigger aria-label="选择小时">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {HOURS.map((hour) => <SelectItem key={hour} value={hour}>{hour} 时</SelectItem>)}
              </SelectGroup>
            </SelectContent>
          </Select>
          <Select value={pad(selected.getMinutes())} onValueChange={(next) => changeTime("minute", next)}>
            <SelectTrigger aria-label="选择分钟">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {MINUTES.map((minute) => <SelectItem key={minute} value={minute}>{minute} 分</SelectItem>)}
              </SelectGroup>
            </SelectContent>
          </Select>
          <Button type="button" variant="outline" size="sm" onClick={useNow}>现在</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export { DateTimePicker };
