import * as React from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker, getDefaultClassNames } from "react-day-picker";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type CalendarProps = React.ComponentProps<typeof DayPicker> & {
  buttonVariant?: React.ComponentProps<typeof Button>["variant"];
};

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  captionLayout = "label",
  buttonVariant = "ghost",
  components,
  ...props
}: CalendarProps) {
  const defaultClassNames = getDefaultClassNames();

  return (
    <DayPicker
      data-slot="calendar"
      showOutsideDays={showOutsideDays}
      captionLayout={captionLayout}
      className={cn("sj-calendar", className)}
      classNames={{
        root: cn("sj-calendar-root", defaultClassNames.root),
        months: cn("sj-calendar-months", defaultClassNames.months),
        month: cn("sj-calendar-month", defaultClassNames.month),
        nav: cn("sj-calendar-nav", defaultClassNames.nav),
        button_previous: cn(buttonVariants({ variant: buttonVariant, size: "icon-sm" }), "sj-calendar-nav-button", defaultClassNames.button_previous),
        button_next: cn(buttonVariants({ variant: buttonVariant, size: "icon-sm" }), "sj-calendar-nav-button", defaultClassNames.button_next),
        month_caption: cn("sj-calendar-caption", defaultClassNames.month_caption),
        caption_label: cn("sj-calendar-caption-label", defaultClassNames.caption_label),
        dropdowns: cn("sj-calendar-dropdowns", defaultClassNames.dropdowns),
        dropdown_root: cn("sj-calendar-dropdown-root", defaultClassNames.dropdown_root),
        dropdown: cn("sj-calendar-dropdown", defaultClassNames.dropdown),
        month_grid: cn("sj-calendar-grid", defaultClassNames.month_grid),
        weekdays: cn("sj-calendar-weekdays", defaultClassNames.weekdays),
        weekday: cn("sj-calendar-weekday", defaultClassNames.weekday),
        week: cn("sj-calendar-week", defaultClassNames.week),
        day: cn("sj-calendar-day", defaultClassNames.day),
        day_button: cn(buttonVariants({ variant: "ghost", size: "icon-sm" }), "sj-calendar-day-button", defaultClassNames.day_button),
        selected: cn("sj-calendar-day-selected", defaultClassNames.selected),
        today: cn("sj-calendar-day-today", defaultClassNames.today),
        outside: cn("sj-calendar-day-outside", defaultClassNames.outside),
        disabled: cn("sj-calendar-day-disabled", defaultClassNames.disabled),
        hidden: cn("sj-calendar-day-hidden", defaultClassNames.hidden),
        range_start: cn("sj-calendar-day-range-start", defaultClassNames.range_start),
        range_middle: cn("sj-calendar-day-range-middle", defaultClassNames.range_middle),
        range_end: cn("sj-calendar-day-range-end", defaultClassNames.range_end),
        ...classNames
      }}
      components={{
        Chevron: ({ className, orientation, ...chevronProps }) => {
          const Icon = orientation === "left" ? ChevronLeft : orientation === "right" ? ChevronRight : ChevronDown;
          return <Icon className={cn("sj-calendar-chevron", className)} {...chevronProps} />;
        },
        ...components
      }}
      {...props}
    />
  );
}

export { Calendar };
