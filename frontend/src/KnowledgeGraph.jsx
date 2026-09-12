import { useMemo, useState } from 'react';

export default function KnowledgeGraph({ graph = { nodes: [], edges: [] } }) {
  const [selected, setSelected] = useState(null);
  const nodes = (graph.nodes || []).slice(0, 18);
  const positions = useMemo(() => nodes.map((node, index) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
    return { ...node, x: 160 + Math.cos(angle) * 112, y: 145 + Math.sin(angle) * 92 };
  }), [nodes]);
  const selectedEdges = (graph.edges || []).filter((edge) => !selected || edge.source === selected || edge.target === selected);
  const nodeById = Object.fromEntries(positions.map((node) => [node.id, node]));

  return <div className="graph-wrap">
    <svg className="knowledge-graph" viewBox="0 0 320 290" role="img" aria-label="Interactive knowledge graph">
      {selectedEdges.map((edge, index) => nodeById[edge.source] && nodeById[edge.target] ? <line key={`${edge.source}-${edge.target}-${index}`} x1={nodeById[edge.source].x} y1={nodeById[edge.source].y} x2={nodeById[edge.target].x} y2={nodeById[edge.target].y} /> : null)}
      {positions.map((node) => <g key={node.id} className={selected === node.id ? 'selected' : ''} onClick={() => setSelected(selected === node.id ? null : node.id)} tabIndex="0" role="button" aria-label={`Select ${node.id}`} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') setSelected(selected === node.id ? null : node.id); }}>
        <circle cx={node.x} cy={node.y} r={Math.min(18, 8 + node.mentions)} /><text x={node.x} y={node.y + 3}>{node.id.slice(0, 13)}</text>
      </g>)}
    </svg>
    <small>{selected ? `Selected: ${selected}` : 'Select an entity to highlight its relationships.'}</small>
  </div>;
}
