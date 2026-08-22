import { useRef } from 'react'
import { ArrowUpIcon, PlusIcon } from 'lucide-react'

import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from '@/components/ui/input-group'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export type ChatComposerAction =
  | { label: string; onSelect: () => void }
  | { label: string; accept?: string; onFile: (file: File) => void }

export type ChatComposerProps = {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled?: boolean
  placeholder?: string
  error?: string
  autoFocus?: boolean
  /** Items for the + menu. Empty or omitted keeps the plus button inactive. */
  actions?: ChatComposerAction[]
}

function isFileAction(
  action: ChatComposerAction,
): action is Extract<ChatComposerAction, { onFile: (file: File) => void }> {
  return 'onFile' in action
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder = 'Describe what happened, or correct a figure…',
  error,
  autoFocus,
  actions,
}: ChatComposerProps) {
  const canSend = !disabled && value.trim().length > 0
  const menuActions = actions ?? []
  const plusEnabled = !disabled && menuActions.length > 0
  const fileInputs = useRef(new Map<string, HTMLInputElement>())

  function submit() {
    if (!canSend) return
    onSubmit()
  }

  function runAction(action: ChatComposerAction) {
    if (isFileAction(action)) {
      fileInputs.current.get(action.label)?.click()
      return
    }
    action.onSelect()
  }

  return (
    <div className="w-full space-y-2">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {menuActions.filter(isFileAction).map((action) => (
        <input
          key={action.label}
          ref={(node) => {
            if (node) fileInputs.current.set(action.label, node)
            else fileInputs.current.delete(action.label)
          }}
          type="file"
          accept={action.accept ?? '.csv,text/csv'}
          aria-label={`Choose ${action.label} file`}
          className="sr-only"
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) action.onFile(file)
          }}
        />
      ))}
      <InputGroup className="h-auto rounded-2xl bg-background ring-[0.3px] shadow-xl">
        <InputGroupTextarea
          autoFocus={autoFocus}
          rows={3}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
        />
        <InputGroupAddon align="block-end" className="justify-between">
          {plusEnabled ? (
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Add"
                render={<InputGroupButton size="icon-sm" />}
              >
                <PlusIcon />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="top" className="w-auto min-w-44">
                {menuActions.map((action) => (
                  <DropdownMenuItem key={action.label} onClick={() => runAction(action)}>
                    {action.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <InputGroupButton
              size="icon-sm"
              disabled
              aria-label="Add"
            >
              <PlusIcon />
            </InputGroupButton>
          )}
          <InputGroupButton
            size="icon-sm"
            variant="default"
            disabled={!canSend}
            aria-label="Send"
            onClick={submit}
          >
            <ArrowUpIcon />
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </div>
  )
}
