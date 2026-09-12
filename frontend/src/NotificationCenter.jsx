import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import { ragApiRequest } from './api';

export default function NotificationCenter() {
  const [open, setOpen] = useState(false); const [items, setItems] = useState([]);
  const load = async () => { try { const data = await ragApiRequest('/api/notifications'); setItems(data.notifications || []); } catch { /* API may be offline */ } };
  useEffect(() => {
    const starter = window.setTimeout(() => { void load(); }, 0);
    const timer = window.setInterval(load, 30000);
    return () => { window.clearTimeout(starter); window.clearInterval(timer); };
  }, []);
  const markRead = async (item) => { await ragApiRequest(`/api/notifications/${item.id}/read`, { method: 'POST' }); await load(); };
  return <div className="notification-center"><button className="icon-button" type="button" aria-label="Notifications" onClick={() => { setOpen(!open); if (!open) void load(); }}><Bell size={17} />{items.some((item) => !item.read) ? <i /> : null}</button>{open ? <div className="notification-popover">{items.length ? items.map((item) => <button type="button" key={item.id} className={item.read ? '' : 'unread'} onClick={() => void markRead(item)}><strong>{item.title}</strong><small>{item.detail}</small></button>) : <small>No notifications</small>}</div> : null}</div>;
}
