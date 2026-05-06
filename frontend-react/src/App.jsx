import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Chat from './pages/Chat';
import BatchUpload from './pages/BatchUpload';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-background font-sans text-foreground">
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/batch-upload" element={<BatchUpload />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
