import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { fetchParts } from '../api/endpoints'
import { useAuth } from '../context/AuthContext'
import type { PartListRow } from '../types'

const PAGE_SIZE = 25

export function PartsPage() {
  const { user, logout } = useAuth()

  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)

  const [items, setItems] = useState<PartListRow[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadParts() {
      setIsLoading(true)
      setErrorMessage('')

      try {
        const response = await fetchParts({ q: query, page, pageSize: PAGE_SIZE })
        if (!cancelled) {
          setItems(response.results)
          setTotalCount(response.count)
        }
      } catch {
        if (!cancelled) {
          setErrorMessage('Failed to load parts. Please refresh or sign in again.')
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadParts()
    return () => {
      cancelled = true
    }
  }, [query, page])

  const pageCount = useMemo(() => {
    const computed = Math.ceil(totalCount / PAGE_SIZE)
    return computed > 0 ? computed : 1
  }, [totalCount])

  function onSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPage(1)
    setQuery(searchInput.trim())
  }

  async function onLogoutClick() {
    await logout()
  }

  return (
    <main className="shell">
      <section className="panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">Parts Workspace</p>
            <h1>Dashboard</h1>
            <p className="muted">
              {user?.profile?.organization?.name || 'No organization'}
              {' • '}
              {user?.profile?.role_display || 'No role'}
            </p>
          </div>
          <button className="ghost" onClick={onLogoutClick} type="button">
            Sign Out
          </button>
        </header>

        <form className="searchbar" onSubmit={onSearchSubmit}>
          <input
            placeholder="Search by part number, synopsis, or manufacturer"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <button type="submit">Search</button>
        </form>

        {errorMessage && <p className="error">{errorMessage}</p>}
        {isLoading && <p className="status">Loading parts...</p>}

        {!isLoading && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Part Number</th>
                  <th>Class</th>
                  <th>Revision</th>
                  <th>Description</th>
                  <th>Manufacturer</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="status">
                      No parts found.
                    </td>
                  </tr>
                )}

                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link className="text-link" to={`/parts/${item.part_id}`}>
                        {item.part_number}
                      </Link>
                    </td>
                    <td>{item.part_class ? `${item.part_class.code} - ${item.part_class.name}` : '-'}</td>
                    <td>{item.revision}</td>
                    <td>{item.description || item.synopsis || '-'}</td>
                    <td>
                      {item.primary_manufacturer_name || '-'}
                      {item.primary_manufacturer_part_number ? ` (${item.primary_manufacturer_part_number})` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="pager">
          <button type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>
            Previous
          </button>
          <span>
            Page {page} / {pageCount}
          </span>
          <button
            type="button"
            disabled={page >= pageCount}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </button>
        </footer>
      </section>
    </main>
  )
}