import { format, parse, isValid, startOfDay } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import { Button } from '@dth/ui/components/button'
import { Calendar } from '@dth/ui/components/calendar'
import { Field, FieldDescription, FieldLabel } from '@dth/ui/components/field'
import { Popover, PopoverContent, PopoverTrigger } from '@dth/ui/components/popover'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'
import { cn } from '@dth/ui/lib/utils'

type Props = {
  label: string
  labelClassName?: string
  helpText?: string
  helpTextAbove?: boolean
  helpTextClassName?: string
  buttonClassName?: string
  required?: boolean
  placeholder?: string
  disabled?: boolean
  minDate?: Date
  maxDate?: Date
  captionLayout?: 'label' | 'dropdown' | 'dropdown-months' | 'dropdown-years' | undefined
}

export const DatePickerField = ({
  label,
  labelClassName,
  helpText,
  helpTextAbove,
  helpTextClassName,
  buttonClassName,
  required,
  placeholder = 'Pick a date',
  disabled,
  minDate,
  maxDate,
}: Props) => {
  const field = useFieldContext<string | null>()

  const dateValue =
    field.state.value && typeof field.state.value === 'string'
      ? parse(field.state.value, 'yyyy-MM-dd', new Date())
      : undefined

  const isValidDate = dateValue && isValid(dateValue) ? dateValue : undefined

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>
      {helpText}
    </FieldDescription>
  ) : null

  return (
    <Field className="w-full max-w-3xs gap-1.5">
      <FieldLabel htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </FieldLabel>
      {helpTextAbove && helpTextEl}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            id={field.name}
            variant="outline"
            disabled={disabled}
            className={cn(
              'w-full justify-start text-left font-normal',
              !isValidDate && 'text-muted-foreground',
              buttonClassName,
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {isValidDate ? format(isValidDate, 'PPP') : placeholder}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={isValidDate}
            defaultMonth={isValidDate}
            captionLayout="dropdown"
            onSelect={(date) => {
              field.handleChange(date ? format(date, 'yyyy-MM-dd') : null)
            }}
            disabled={(date) => {
              const day = startOfDay(date)
              if (minDate && day < startOfDay(minDate)) return true
              if (maxDate && day > startOfDay(maxDate)) return true
              return false
            }}
            initialFocus
          />
        </PopoverContent>
      </Popover>
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}
