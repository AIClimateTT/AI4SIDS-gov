import { Input } from "@dth/ui/components/input"
import { Field, FieldDescription, FieldLabel } from "@dth/ui/components/field"
import { Label } from "@dth/ui/components/label"
import { Eye, EyeOff } from "lucide-react"
import { useState, type JSX } from "react"
import { useFieldContext } from "../hooks/contexts"
import { FieldErrors } from "./field-error"
import * as React from "react"
import { cn } from "@dth/ui/lib/utils"
import PhoneInput from "react-phone-number-input"
import "react-phone-number-input/style.css"

type Props = {
  label: string | JSX.Element
  type?:
    | "text"
    | "email"
    | "password"
    | "url"
    | "number"
    | "date"
    | "time"
    | "datetime-local"
    | "tel"
  required?: boolean
  placeholder?: string
  autoComplete?: string
  helpText?: string
  helpTextAbove?: boolean
  helpTextClassName?: string
  labelClassName?: string
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  value?: string | number
}

export const TextField = ({
  label,
  type = "text",
  required,
  placeholder,
  autoComplete,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
  min,
  max,
  step,
  disabled,
  value,
}: Props) => {
  const field = useFieldContext<string | number | null>()

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>
      {helpText}
    </FieldDescription>
  ) : null

 
  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </FieldLabel>
      {helpTextAbove && helpTextEl}
        <Input
          name={field.name}
          id={field.name}
          value={value ?? field.state.value ?? ""}
          onChange={(e) =>
            type === "number"
              ? field.handleChange(e.target.valueAsNumber)
              : field.handleChange(e.target.value)
          }
          onBlur={field.handleBlur}
          type={type}
          placeholder={placeholder}
          autoComplete={autoComplete}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          aria-invalid={
            field.state.meta.isTouched && field.state.meta.errors.length > 0
          }
          className="bg-background"
        />
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}

export const PasswordTextField = ({
  label,
  required,
  placeholder,
  autoComplete,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
  value,
}: Props) => {
  const field = useFieldContext<string | number | null>()
  const [showPassword, setShowPassword] = useState(false)

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>
      {helpText}
    </FieldDescription>
  ) : null

  return (
    <div className="flex w-full flex-col gap-2">
      <Label htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      {helpTextAbove && helpTextEl}
      <div className="relative">
        <Input
          name={field.name}
          id={field.name}
          value={value ?? field.state.value ?? ""}
          onChange={(e) => field.handleChange(e.target.value)}
          onBlur={field.handleBlur}
          type={showPassword ? "text" : "password"}
          placeholder={placeholder}
          autoComplete={autoComplete}
          aria-invalid={
            field.state.meta.isTouched && field.state.meta.errors.length > 0
          }
          className="bg-background"
        />
        <button
          type="button"
          className="absolute top-0 right-0 h-full px-3 py-2 text-muted-foreground hover:text-foreground"
          onClick={() => setShowPassword(!showPassword)}
          tabIndex={-1}
          aria-label={showPassword ? "Hide password" : "Show password"}
        >
          {showPassword ? (
            <EyeOff className="size-4" />
          ) : (
            <Eye className="size-4" />
          )}
        </button>
      </div>
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </div>
  )
}

const PhoneNumberInput = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40",
          className,
        )}
        {...props}
      />
    )
  },
)

PhoneNumberInput.displayName = "PhoneNumberInput"

export const PhoneTextField = ({
  label,
  required,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
}: Props) => {
  const field = useFieldContext<string | number | null>()

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>
      {helpText}
    </FieldDescription>
  ) : null

  return (
    <div className="flex w-full flex-col gap-2">
      <Label htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </Label>
      {helpTextAbove && helpTextEl}
      <PhoneInput
        // defaultCountry="TT"
        international
        withCountryCallingCode
        placeholder="eg. +1 868 123 4567"
        value={(field.state.value as string) || undefined}
        onChange={(value) => field.handleChange(value ?? "")}
        onBlur={field.handleBlur}
        inputComponent={PhoneNumberInput}
        className="max-w-xs"
        numberInputProps={{
          className: "bg-white",
        }}
      />
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </div>
  )
}
