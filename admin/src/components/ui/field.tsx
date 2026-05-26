import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

function FieldGroup({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="field-group" className={cn("sj-field-group", className)} {...props} />;
}

type FieldProps = ComponentProps<"div"> & {
  orientation?: "vertical" | "horizontal" | "responsive";
};

function Field({ className, orientation = "vertical", ...props }: FieldProps) {
  return (
    <div
      data-slot="field"
      data-orientation={orientation}
      className={cn("sj-field", className)}
      {...props}
    />
  );
}

function FieldContent({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="field-content" className={cn("sj-field-content", className)} {...props} />;
}

function FieldLabel({ className, ...props }: ComponentProps<"label">) {
  return <label data-slot="field-label" className={cn("sj-field-label", className)} {...props} />;
}

function FieldDescription({ className, ...props }: ComponentProps<"p">) {
  return (
    <p
      data-slot="field-description"
      className={cn("sj-field-description", className)}
      {...props}
    />
  );
}

function FieldError({ className, ...props }: ComponentProps<"p">) {
  return <p data-slot="field-error" className={cn("sj-field-error", className)} {...props} />;
}

function FieldSeparator({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="field-separator"
      className={cn("sj-field-separator", className)}
      role="separator"
      {...props}
    />
  );
}

function FieldSet({ className, ...props }: ComponentProps<"fieldset">) {
  return <fieldset data-slot="field-set" className={cn("sj-field-set", className)} {...props} />;
}

function FieldLegend({ className, ...props }: ComponentProps<"legend">) {
  return <legend data-slot="field-legend" className={cn("sj-field-legend", className)} {...props} />;
}

export {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSeparator,
  FieldSet
};
export type { FieldProps };
