import { DownloadIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { downloadCaptureTranscript } from '@/lib/api/admin-capture'
import type { TranscriptFormat } from '@/lib/api/admin-capture'

/** Admin export of a capture session: chat, captured facts and the generated sitrep. */
export function TranscriptMenu({ sessionId }: { sessionId: number }) {
  const [busy, setBusy] = useState(false)

  async function download(format: TranscriptFormat) {
    setBusy(true)
    try {
      await downloadCaptureTranscript(sessionId, format)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not export transcript')
    } finally {
      setBusy(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={busy}
        render={<Button type="button" variant="ghost" size="sm" />}
      >
        <DownloadIcon className="size-3.5" />
        Transcript
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => void download('md')}>
          Readable (.md)
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => void download('json')}>
          Data (.json)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
