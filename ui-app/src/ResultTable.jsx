export default function ResultTable({ result }) {
  if (!result || !result.columns?.length) return null;
  const { columns, rows, row_count } = result;

  return (
    <div className="result">
      <div className="result-meta">{row_count} row{row_count === 1 ? "" : "s"}</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={i}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <td key={ci}>{cell === null ? "∅" : String(cell)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
