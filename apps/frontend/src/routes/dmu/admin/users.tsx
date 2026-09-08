import { useMemo, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Pencil, Plus, Trash2, UserCheck, UserX } from 'lucide-react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AppDialog,
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { RoleMismatchNotice } from '@/components/identity/role-mismatch-notice'
import { useAppForm } from '@/hooks/form'
import { formatWhen } from '@/lib/format-when'
import {
  useActivateUser,
  useCreateUser,
  useDeactivateUser,
  useDeleteUser,
  useUpdateUser,
  userQueries,
} from '@/lib/queries/users'
import { currentUserIdFromToken, userDisplayName } from '@/lib/users'
import type { UserAccount } from '@/types/users'

export const Route = createFileRoute('/dmu/admin/users')({
  component: UsersPage,
})

const userFormSchema = z.object({
  email: z.email('Enter a valid email'),
  first_name: z.string(),
  last_name: z.string(),
})

function UsersPage() {
  const { data, isPending, isError, error } = useQuery(userQueries.list())
  const activateUser = useActivateUser()
  const deactivateUser = useDeactivateUser()
  const deleteUser = useDeleteUser()
  const currentUserId = useMemo(
    () =>
      currentUserIdFromToken(
        typeof window === 'undefined'
          ? null
          : window.localStorage.getItem('auth_token'),
      ),
    [],
  )

  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<UserAccount | null>(null)
  const [pendingDelete, setPendingDelete] = useState<UserAccount | null>(null)

  function openCreate() {
    setEditing(null)
    setEditorOpen(true)
  }

  function openEdit(user: UserAccount) {
    setEditing(user)
    setEditorOpen(true)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        description="Add and manage Disaster Management Unit accounts. New users sign in with an email OTP."
        actions={
          <Button onClick={openCreate}>
            <Plus data-icon="inline-start" />
            Add user
          </Button>
        }
      />
      <RoleMismatchNotice expected="dmu" />

      {isPending ? <LoadingBlock rows={4} /> : null}

      {isError ? (
        <EmptyState title="Could not load users" description={error.message} />
      ) : null}

      {data ? (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last login</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No DMU users yet.
                  </TableCell>
                </TableRow>
              ) : (
                data.map((user) => {
                  const isSelf = currentUserId === user.user_id
                  return (
                    <TableRow key={user.user_id}>
                      <TableCell>{userDisplayName(user)}</TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>
                        <Badge variant={user.is_active ? 'default' : 'secondary'}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {user.last_login
                          ? formatWhen(user.last_login)
                          : 'Never'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEdit(user)}
                            aria-label={`Edit ${user.email}`}
                          >
                            <Pencil />
                          </Button>
                          {user.is_active ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={isSelf || deactivateUser.isPending}
                              onClick={() =>
                                deactivateUser.mutate(user.user_id)
                              }
                              aria-label={`Deactivate ${user.email}`}
                            >
                              <UserX />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={activateUser.isPending}
                              onClick={() => activateUser.mutate(user.user_id)}
                              aria-label={`Activate ${user.email}`}
                            >
                              <UserCheck />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={isSelf}
                            onClick={() => setPendingDelete(user)}
                            aria-label={`Delete ${user.email}`}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>
      ) : null}

      <AppDialog
        open={editorOpen}
        onOpenChange={(open) => {
          setEditorOpen(open)
          if (!open) setEditing(null)
        }}
        title={editing ? 'Edit user' : 'Add user'}
        description={
          editing
            ? 'Update this DMU account. Email changes take effect on the next sign-in.'
            : 'Creates an active DMU account. They can request an OTP immediately.'
        }
      >
        {editorOpen ? (
          <UserEditor
            key={editing?.user_id ?? 'new'}
            user={editing}
            onClose={() => {
              setEditorOpen(false)
              setEditing(null)
            }}
          />
        ) : null}
      </AppDialog>

      <AppDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        title="Delete this user?"
        description={
          pendingDelete
            ? `This permanently removes ${pendingDelete.email} and ends any active sessions.`
            : null
        }
        footer={
          <>
            <Button variant="outline" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (!pendingDelete) return
                deleteUser.mutate(pendingDelete.user_id)
                setPendingDelete(null)
              }}
            >
              Delete
            </Button>
          </>
        }
      />
    </div>
  )
}

function UserEditor({
  user,
  onClose,
}: {
  user: UserAccount | null
  onClose: () => void
}) {
  const createUser = useCreateUser(onClose)
  const updateUser = useUpdateUser(onClose)

  const form = useAppForm({
    defaultValues: {
      email: user?.email ?? '',
      first_name: user?.first_name ?? '',
      last_name: user?.last_name ?? '',
    },
    validators: { onSubmit: userFormSchema },
    onSubmit: async ({ value }) => {
      const payload = {
        email: value.email.trim(),
        first_name: value.first_name.trim() || null,
        last_name: value.last_name.trim() || null,
      }
      if (user) {
        await updateUser.mutateAsync({ userId: user.user_id, data: payload })
      } else {
        await createUser.mutateAsync(payload)
      }
    },
  })

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        event.stopPropagation()
        void form.handleSubmit()
      }}
    >
      <form.AppForm>
        <form.AppField name="email">
          {(field) => (
            <field.TextField label="Email" type="email" required />
          )}
        </form.AppField>
        <form.AppField name="first_name">
          {(field) => <field.TextField label="First name" />}
        </form.AppField>
        <form.AppField name="last_name">
          {(field) => <field.TextField label="Last name" />}
        </form.AppField>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <form.SubmitButton label={user ? 'Save' : 'Create'} />
        </div>
      </form.AppForm>
    </form>
  )
}
