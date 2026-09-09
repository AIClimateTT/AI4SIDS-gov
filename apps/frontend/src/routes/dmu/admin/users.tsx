import { useMemo, useState, type ReactNode } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { KeyRound, Pencil, Plus, Trash2, UserCheck, UserX } from 'lucide-react'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  AppDialog,
  EmptyState,
  LoadingBlock,
  PageHeader,
} from '@/components/shared'
import { ContentCard } from '@/components/shared/content-card'
import { DataTable } from '@/components/data-table'
import { useAppForm } from '@/hooks/form'
import { formatWhen } from '@/lib/format-when'
import {
  useActivateUser,
  useCreateUser,
  useDeactivateUser,
  useDeleteUser,
  useSetUserPassword,
  useUpdateUser,
  userQueries,
} from '@/lib/queries/users'
import { useOptionalAuth } from '@/lib/auth/auth-context'
import {
  CORPORATION_OPTIONS,
  isCanonicalCorporation,
} from '@/lib/corporations'
import { corporationDisplayName, userDisplayName } from '@/lib/users'
import type { UserAccount } from '@/types/users'

export const Route = createFileRoute('/dmu/admin/users')({
  component: UsersPage,
})

const userFormSchema = z.object({
  email: z.email('Enter a valid email'),
  first_name: z.string(),
  last_name: z.string(),
})

const createUserFormSchema = userFormSchema
  .extend({
    role: z.enum(['dmu', 'admin', 'corp']),
    corporation: z.string(),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string(),
  })
  .refine((value) => value.password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })
  .superRefine((value, ctx) => {
    if (value.role === 'corp' && !isCanonicalCorporation(value.corporation)) {
      ctx.addIssue({
        code: 'custom',
        path: ['corporation'],
        message: 'Select a corporation',
      })
    }
  })

const editCorpUserFormSchema = userFormSchema.extend({
  corporation: z
    .string()
    .refine(isCanonicalCorporation, 'Select a corporation'),
})

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string(),
  })
  .refine((value) => value.password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

const ROLE_OPTIONS = [
  { value: 'all' as const, label: 'All' },
  { value: 'dmu' as const, label: 'Officer' },
  { value: 'admin' as const, label: 'Admin' },
  { value: 'corp' as const, label: 'Corporation' },
]

function roleLabel(role: string): string {
  if (role === 'admin') return 'Admin'
  if (role === 'dmu') return 'Officer'
  if (role === 'corp') return 'Corporation'
  return role
}

const columns: ColumnDef<UserAccount>[] = [
  {
    id: 'name',
    accessorFn: (user) => userDisplayName(user),
    header: 'Name',
  },
  {
    accessorKey: 'email',
    header: 'Email',
  },
  {
    accessorKey: 'role',
    header: 'Role',
    cell: ({ row }) => roleLabel(row.original.role),
  },
  {
    id: 'corporation',
    accessorFn: (user) => corporationDisplayName(user.corporation),
    header: 'Corporation',
    cell: ({ row }) => corporationDisplayName(row.original.corporation),
  },
  {
    id: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <div className="flex flex-wrap gap-1">
        <Badge variant={row.original.is_active ? 'default' : 'secondary'}>
          {row.original.is_active ? 'Active' : 'Inactive'}
        </Badge>
        {row.original.has_password ? null : (
          <Badge variant="outline">No password</Badge>
        )}
      </div>
    ),
  },
  {
    accessorKey: 'last_login',
    header: 'Last login',
    cell: ({ row }) =>
      row.original.last_login ? formatWhen(row.original.last_login) : 'Never',
  },
]

function UsersPage() {
  const { data, isPending, isError, error } = useQuery(userQueries.list())
  const activateUser = useActivateUser()
  const deactivateUser = useDeactivateUser()
  const deleteUser = useDeleteUser()
  const currentUserId = useOptionalAuth()?.session?.userId ?? null

  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  })
  const [q, setQ] = useState<string | undefined>()
  const [role, setRole] = useState<'all' | 'dmu' | 'admin' | 'corp'>('all')
  const [corporation, setCorporation] = useState<string | undefined>()
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<UserAccount | null>(null)
  const [pendingDelete, setPendingDelete] = useState<UserAccount | null>(null)
  const [resetting, setResetting] = useState<UserAccount | null>(null)

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
        description="Add and manage DMU officers, admins, and corporation accounts. Any number of people can be appointed to the same corporation. Share the password out of band — there is no email reset."
        actions={
          <Button onClick={openCreate}>
            <Plus data-icon="inline-start" />
            Add user
          </Button>
        }
      />

      <ContentCard contentClassName="space-y-4">
        {isPending && !data ? <LoadingBlock rows={5} /> : null}

        {isError ? (
          <EmptyState title="Could not load users" description={error.message} />
        ) : null}

        {data ? (
          <UsersTable
            users={data}
            pagination={pagination}
            q={q}
            role={role}
            corporation={corporation}
            currentUserId={currentUserId}
            isActivating={activateUser.isPending}
            isDeactivating={deactivateUser.isPending}
            onStateChange={(updates) => {
              if (typeof updates.page === 'number') {
                const page = updates.page
                setPagination((prev) => ({
                  ...prev,
                  pageIndex: Math.max(page - 1, 0),
                }))
              }
              const nextPageSize = updates.pageSize ?? updates.page_size
              if (typeof nextPageSize === 'number') {
                setPagination({ pageIndex: 0, pageSize: nextPageSize })
              }
              if ('q' in updates) {
                setQ(
                  typeof updates.q === 'string' && updates.q.length > 0
                    ? updates.q
                    : undefined,
                )
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }
              if ('role' in updates) {
                const next =
                  updates.role === 'dmu' ||
                  updates.role === 'admin' ||
                  updates.role === 'corp'
                    ? updates.role
                    : 'all'
                setRole(next)
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }
              if ('corporation' in updates) {
                setCorporation(
                  typeof updates.corporation === 'string' &&
                    updates.corporation.length > 0 &&
                    updates.corporation !== 'all'
                    ? updates.corporation
                    : undefined,
                )
                setPagination((prev) => ({ ...prev, pageIndex: 0 }))
              }
            }}
            onEdit={openEdit}
            onResetPassword={setResetting}
            onActivate={(user) => activateUser.mutate(user.user_id)}
            onDeactivate={(user) => deactivateUser.mutate(user.user_id)}
            onDelete={setPendingDelete}
          />
        ) : null}
      </ContentCard>

      <AppDialog
        open={editorOpen}
        onOpenChange={(open) => {
          setEditorOpen(open)
          if (!open) setEditing(null)
        }}
        title={editing ? 'Edit user' : 'Add user'}
        description={
          editing
            ? 'Update this account. Email and corporation changes take effect on the next sign-in.'
            : 'Creates an active account. Share the password with them out of band.'
        }
      >
        {editorOpen ? (
          editing ? (
            <EditUserForm
              key={editing.user_id}
              user={editing}
              onClose={() => {
                setEditorOpen(false)
                setEditing(null)
              }}
            />
          ) : (
            <CreateUserForm
              onClose={() => {
                setEditorOpen(false)
                setEditing(null)
              }}
            />
          )
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

      <AppDialog
        open={Boolean(resetting)}
        onOpenChange={(open) => {
          if (!open) setResetting(null)
        }}
        title="Reset password"
        description={
          resetting
            ? `Set a new password for ${resetting.email}. Share it out of band. Existing sessions will be signed out.`
            : null
        }
      >
        {resetting ? (
          <ResetPasswordForm
            key={resetting.user_id}
            user={resetting}
            onClose={() => setResetting(null)}
          />
        ) : null}
      </AppDialog>
    </div>
  )
}

function matchesUserQuery(user: UserAccount, q?: string): boolean {
  const needle = q?.trim().toLowerCase()
  if (!needle) return true
  const name = userDisplayName(user).toLowerCase()
  const corporation = corporationDisplayName(user.corporation).toLowerCase()
  return (
    name.includes(needle) ||
    user.email.toLowerCase().includes(needle) ||
    roleLabel(user.role).toLowerCase().includes(needle) ||
    corporation.includes(needle)
  )
}

function IconActionButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled?: boolean
  onClick?: () => void
  children: ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger render={<span className="inline-flex" />}>
        <Button
          variant="ghost"
          size="icon"
          disabled={disabled}
          onClick={onClick}
          aria-label={label}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

function UsersTable({
  users,
  pagination,
  q,
  role,
  corporation,
  currentUserId,
  isActivating,
  isDeactivating,
  onStateChange,
  onEdit,
  onResetPassword,
  onActivate,
  onDeactivate,
  onDelete,
}: {
  users: UserAccount[]
  pagination: { pageIndex: number; pageSize: number }
  q?: string
  role: 'all' | 'dmu' | 'admin' | 'corp'
  corporation?: string
  currentUserId: string | null
  isActivating: boolean
  isDeactivating: boolean
  onStateChange: (updates: Record<string, any>) => void
  onEdit: (user: UserAccount) => void
  onResetPassword: (user: UserAccount) => void
  onActivate: (user: UserAccount) => void
  onDeactivate: (user: UserAccount) => void
  onDelete: (user: UserAccount) => void
}) {
  const filtered = useMemo(
    () =>
      users.filter((user) => {
        if (role !== 'all' && user.role !== role) return false
        if (corporation && user.corporation !== corporation) return false
        return matchesUserQuery(user, q)
      }),
    [users, q, role, corporation],
  )

  const pageItems = useMemo(() => {
    const start = pagination.pageIndex * pagination.pageSize
    return filtered.slice(start, start + pagination.pageSize)
  }, [filtered, pagination.pageIndex, pagination.pageSize])

  return (
    <DataTable
      columns={columns}
      data={pageItems}
      total={filtered.length}
      pagination={pagination}
      onStateChange={onStateChange}
      toolbar={{
        search: {
          key: 'q',
          placeholder: 'Search users…',
        },
      }}
      filters={[
        {
          type: 'toggle',
          key: 'role',
          label: 'Role',
          options: ROLE_OPTIONS,
        },
        {
          type: 'select',
          key: 'corporation',
          label: 'Corporation',
          options: CORPORATION_OPTIONS,
        },
      ]}
      filterValues={{ q, role, corporation }}
      features={{
        enablePageSizeSelector: true,
        enableColumnVisibility: true,
      }}
      rowActions={(user) => {
        const isSelf = currentUserId === user.user_id
        return (
          <div className="flex justify-end gap-1">
            <IconActionButton
              label="Edit"
              onClick={() => onEdit(user)}
            >
              <Pencil />
            </IconActionButton>
            <IconActionButton
              label="Reset password"
              onClick={() => onResetPassword(user)}
            >
              <KeyRound />
            </IconActionButton>
            {user.is_active ? (
              <IconActionButton
                label={
                  isSelf
                    ? 'You cannot deactivate your own account'
                    : 'Deactivate'
                }
                disabled={isSelf || isDeactivating}
                onClick={() => onDeactivate(user)}
              >
                <UserX />
              </IconActionButton>
            ) : (
              <IconActionButton
                label="Activate"
                disabled={isActivating}
                onClick={() => onActivate(user)}
              >
                <UserCheck />
              </IconActionButton>
            )}
            <IconActionButton
              label={
                isSelf ? 'You cannot delete your own account' : 'Delete'
              }
              disabled={isSelf}
              onClick={() => onDelete(user)}
            >
              <Trash2 />
            </IconActionButton>
          </div>
        )
      }}
    />
  )
}

function CreateUserForm({ onClose }: { onClose: () => void }) {
  const createUser = useCreateUser(onClose)
  const form = useAppForm({
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      role: 'dmu' as 'dmu' | 'admin' | 'corp',
      corporation: '',
      password: '',
      confirm_password: '',
    },
    validators: { onSubmit: createUserFormSchema },
    onSubmit: async ({ value }) => {
      await createUser.mutateAsync({
        email: value.email.trim(),
        first_name: value.first_name.trim() || null,
        last_name: value.last_name.trim() || null,
        password: value.password,
        role: value.role,
        corporation:
          value.role === 'corp' ? value.corporation : null,
      })
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
        <form.AppField name="role">
          {(field) => (
            <field.SelectField
              label="Role"
              required
              options={[
                { value: 'dmu', label: 'DMU officer' },
                { value: 'admin', label: 'Admin' },
                { value: 'corp', label: 'Corporation' },
              ]}
            />
          )}
        </form.AppField>
        <form.Subscribe selector={(state) => state.values.role}>
          {(role) =>
            role === 'corp' ? (
              <form.AppField name="corporation">
                {(field) => (
                  <field.SelectField
                    label="Corporation"
                    required
                    placeholder="Select a corporation"
                    options={CORPORATION_OPTIONS}
                  />
                )}
              </form.AppField>
            ) : null
          }
        </form.Subscribe>
        <form.AppField name="password">
          {(field) => (
            <field.TextField
              label="Password"
              type="password"
              required
              helpText="Share this password out of band. It is not emailed."
            />
          )}
        </form.AppField>
        <form.AppField name="confirm_password">
          {(field) => (
            <field.TextField
              label="Confirm password"
              type="password"
              required
            />
          )}
        </form.AppField>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <form.SubmitButton label="Create" />
        </div>
      </form.AppForm>
    </form>
  )
}

function EditUserForm({
  user,
  onClose,
}: {
  user: UserAccount
  onClose: () => void
}) {
  const updateUser = useUpdateUser(onClose)
  const isCorp = user.role === 'corp'
  const form = useAppForm({
    defaultValues: {
      email: user.email,
      first_name: user.first_name ?? '',
      last_name: user.last_name ?? '',
      corporation: user.corporation ?? '',
    },
    validators: {
      onSubmit: isCorp
        ? editCorpUserFormSchema
        : userFormSchema.extend({ corporation: z.string() }),
    },
    onSubmit: async ({ value }) => {
      await updateUser.mutateAsync({
        userId: user.user_id,
        data: {
          email: value.email.trim(),
          first_name: value.first_name.trim() || null,
          last_name: value.last_name.trim() || null,
          ...(isCorp ? { corporation: value.corporation } : {}),
        },
      })
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
        {isCorp ? (
          <form.AppField name="corporation">
            {(field) => (
              <field.SelectField
                label="Corporation"
                required
                options={CORPORATION_OPTIONS}
              />
            )}
          </form.AppField>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <form.SubmitButton label="Save" />
        </div>
      </form.AppForm>
    </form>
  )
}

function ResetPasswordForm({
  user,
  onClose,
}: {
  user: UserAccount
  onClose: () => void
}) {
  const setPassword = useSetUserPassword(onClose)
  const form = useAppForm({
    defaultValues: { password: '', confirm_password: '' },
    validators: { onSubmit: resetPasswordSchema },
    onSubmit: async ({ value }) => {
      await setPassword.mutateAsync({
        userId: user.user_id,
        password: value.password,
      })
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
        <form.AppField name="password">
          {(field) => (
            <field.TextField label="New password" type="password" required />
          )}
        </form.AppField>
        <form.AppField name="confirm_password">
          {(field) => (
            <field.TextField
              label="Confirm password"
              type="password"
              required
            />
          )}
        </form.AppField>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <form.SubmitButton label="Reset password" />
        </div>
      </form.AppForm>
    </form>
  )
}
