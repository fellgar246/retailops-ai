import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  numeric?: boolean;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption: string;
  onRowClick?: (row: T) => void;
  selectedKey?: string | number;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  onRowClick,
  selectedKey,
}: DataTableProps<T>) {
  return (
    <div className="table-wrap">
      <table className="data">
        <caption
          className="muted"
          style={{ captionSide: 'top', padding: '10px 12px', textAlign: 'left' }}
        >
          {caption}
        </caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th className={column.numeric ? 'num' : undefined} key={column.key} scope="col">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row);
            return (
              <tr
                data-href={onRowClick ? 'true' : undefined}
                data-selected={selectedKey === key ? 'true' : undefined}
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
              >
                {columns.map((column) => (
                  <td className={column.numeric ? 'num' : undefined} key={column.key}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
