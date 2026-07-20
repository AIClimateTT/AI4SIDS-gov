import {
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
  ComboboxValue,
  ComboboxGroup,
  ComboboxLabel,
  ComboboxCollection,
  ComboboxSeparator,
} from '@dth/ui/components/combobox'
import { Field, FieldDescription, FieldLabel } from '@dth/ui/components/field'
import { useFieldContext } from '../hooks/contexts'
import { FieldErrors } from './field-error'

type Option = {
  value: string
  label: string
  description?: string
}

type Group = {
  label: string
  items: Option[]
}

type BaseProps = {
  label: string
  required?: boolean
  placeholder?: string
  searchPlaceholder?: string
  emptyMessage?: string
  disabled?: boolean
  helpText?: string
  helpTextAbove?: boolean
  helpTextClassName?: string
  labelClassName?: string
}

type PropsWithOptions = BaseProps & { options: Option[]; groups?: never }
type PropsWithGroups = BaseProps & { options?: never; groups: Group[] }
type Props = PropsWithOptions | PropsWithGroups

export const ComboboxField = ({
  label,
  options,
  groups,
  required,
  placeholder = 'Select an option',
  emptyMessage = 'No results found.',
  disabled,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
}: Props) => {
  const field = useFieldContext<string | null>()

  const allOptions = options ?? groups?.flatMap((g) => g.items) ?? []
  const selectedOption = allOptions.find((opt) => opt.value === field.state.value) ?? null

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>{helpText}</FieldDescription>
  ) : null

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </FieldLabel>
      {helpTextAbove && helpTextEl}
      <Combobox
        items={(groups ?? options) as any}
        value={selectedOption}
        onValueChange={(val) => {
          const stringVal = (val as Option | null)?.value ?? null
          field.handleChange(stringVal)
          field.handleBlur()
        }}
        isItemEqualToValue={(item, val) => item.value === (val as Option)?.value}
      >
        <ComboboxInput placeholder={placeholder} className="bg-background" disabled={disabled} />
        <ComboboxContent>
          <ComboboxEmpty>{emptyMessage}</ComboboxEmpty>
          <ComboboxList>
            {groups
              ? (group: Group, index: number) => (
                  <ComboboxGroup key={group.label} items={group.items}>
                    <ComboboxLabel className="uppercase font-semibold">{group.label}</ComboboxLabel>
                    <ComboboxCollection>
                      {(option: Option) => (
                        <ComboboxItem key={option.value} value={option}>
                          {option.label}
                          {option.description && (
                            <span className="text-xs text-muted-foreground ml-1">
                              — {option.description}
                            </span>
                          )}
                        </ComboboxItem>
                      )}
                    </ComboboxCollection>
                    {index < groups.length - 1 && <ComboboxSeparator />}
                  </ComboboxGroup>
                )
              : (option: Option) => (
                  <ComboboxItem key={option.value} value={option}>
                    {option.label}
                    {option.description && (
                      <span className="text-xs text-muted-foreground ml-1">
                        — {option.description}
                      </span>
                    )}
                  </ComboboxItem>
                )}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}

export const MultiComboboxField = ({
  label,
  options,
  groups,
  required,
  placeholder = 'Add...',
  emptyMessage = 'No results found.',
  disabled,
  helpText,
  helpTextAbove,
  helpTextClassName,
  labelClassName,
}: Props) => {
  const field = useFieldContext<string[]>()

  const allOptions = options ?? groups?.flatMap((g) => g.items) ?? []
  const selectedOptions = allOptions.filter((opt) =>
    (field.state.value ?? []).includes(opt.value),
  )

  const helpTextEl = helpText ? (
    <FieldDescription className={helpTextClassName}>{helpText}</FieldDescription>
  ) : null

  return (
    <Field className="w-full gap-1.5">
      <FieldLabel htmlFor={field.name} className={labelClassName}>
        {label}
        {required && <span className="text-destructive">*</span>}
      </FieldLabel>
      {helpTextAbove && helpTextEl}
      <Combobox
        items={(groups ?? options) as any}
        multiple
        value={selectedOptions}
        onValueChange={(vals) => {
          const stringVals = (vals as Option[]).map((v) => v.value)
          field.handleChange(stringVals)
          field.handleBlur()
        }}
        isItemEqualToValue={(item, val) => item.value === (val as Option)?.value}
      >
        <ComboboxChips>
          <ComboboxValue>
            {selectedOptions.map((opt) => (
              <ComboboxChip key={opt.value}>{opt.label}</ComboboxChip>
            ))}
          </ComboboxValue>
          <ComboboxChipsInput placeholder={placeholder} disabled={disabled} />
        </ComboboxChips>
        <ComboboxContent>
          <ComboboxEmpty>{emptyMessage}</ComboboxEmpty>
          <ComboboxList>
            {groups
              ? (group: Group, index: number) => (
                  <ComboboxGroup key={group.label} items={group.items}>
                    <ComboboxLabel className="uppercase">{group.label}</ComboboxLabel>
                    <ComboboxCollection>
                      {(option: Option) => (
                        <ComboboxItem key={option.value} value={option}>
                          {option.label}
                        </ComboboxItem>
                      )}
                    </ComboboxCollection>
                    {index < groups.length - 1 && <ComboboxSeparator />}
                  </ComboboxGroup>
                )
              : (option: Option) => (
                  <ComboboxItem key={option.value} value={option}>
                    {option.label}
                  </ComboboxItem>
                )}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
      <FieldErrors meta={field.state.meta} />
      {!helpTextAbove && helpTextEl}
    </Field>
  )
}
