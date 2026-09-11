import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'

export type WhatsAppSourceMode = 'paste' | 'upload'

export type WhatsAppSourceInput = {
  asAt: string
  text?: string
  file?: File
}

export type WhatsAppSourceFormProps = {
  onSubmit: (input: WhatsAppSourceInput) => Promise<void> | void
  pending?: boolean
  error?: string
}

function nowDatetimeLocal(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(
    now.getHours(),
  )}:${pad(now.getMinutes())}`
}

export function WhatsAppSourceForm({
  onSubmit,
  pending = false,
  error,
}: WhatsAppSourceFormProps) {
  const [mode, setMode] = useState<WhatsAppSourceMode>('paste')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | undefined>()
  const [asAt, setAsAt] = useState(nowDatetimeLocal)

  const canSubmit =
    !pending &&
    (mode === 'paste' ? text.trim().length > 0 : file != null)

  function handleModeChange(next: string) {
    if (next !== 'paste' && next !== 'upload') return
    setMode(next)
    if (next === 'paste') {
      setFile(undefined)
    } else {
      setText('')
    }
  }

  function submit() {
    if (!canSubmit) return
    if (mode === 'paste') {
      void onSubmit({ asAt, text: text.trim() })
      return
    }
    if (!file) return
    void onSubmit({ asAt, file })
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <Tabs value={mode} onValueChange={handleModeChange}>
        <TabsList>
          <TabsTrigger value="paste">Paste text</TabsTrigger>
          <TabsTrigger value="upload">Upload .txt</TabsTrigger>
        </TabsList>
        <TabsContent value="paste" className="space-y-2 pt-3">
          <Label htmlFor="whatsapp-paste">Paste the hour</Label>
          <Textarea
            id="whatsapp-paste"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste the hour, a forwarded snippet, or anything operational…"
            className="min-h-32"
            disabled={pending}
          />
        </TabsContent>
        <TabsContent value="upload" className="space-y-2 pt-3">
          <Label htmlFor="whatsapp-export">WhatsApp export</Label>
          <Input
            id="whatsapp-export"
            key={mode}
            type="file"
            accept=".txt,text/plain"
            disabled={pending}
            onChange={(event) =>
              setFile(event.target.files?.[0] ?? undefined)
            }
          />
        </TabsContent>
      </Tabs>

      <div className="space-y-2">
        <Label htmlFor="whatsapp-as-at">As at</Label>
        <Input
          id="whatsapp-as-at"
          type="datetime-local"
          required
          value={asAt}
          onChange={(event) => setAsAt(event.target.value)}
          disabled={pending}
        />
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={!canSubmit}>
          {pending ? 'Extracting…' : 'Extract'}
        </Button>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </form>
  )
}
