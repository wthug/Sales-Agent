import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { User, LogIn, Lock } from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      
      const data = await res.json();
      
      if (res.ok && data.token) {
        localStorage.setItem('token', data.token);
        localStorage.setItem('username', data.username);
        navigate('/chat');
      } else {
        setError(data.error || 'Login failed');
      }
    } catch (err) {
      setError('Network error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] ring-1 ring-gray-100">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-50">
            <LogIn className="h-6 w-6 text-blue-600" />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-gray-900">Welcome back</h2>
          <p className="mt-2 text-sm text-gray-500">Please enter your details to sign in.</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-5">
          {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-600">{error}</div>}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700" htmlFor="username">
              Username
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <User className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="username"
                type="text"
                required
                className="block w-full rounded-xl border-gray-200 bg-gray-50/50 py-2.5 pl-10 pr-3 text-sm outline-none transition-all focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100 placeholder:text-gray-400"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-sm font-medium text-gray-700" htmlFor="password">
                Password
              </label>
              <a href="#" className="text-sm font-medium text-blue-600 hover:text-blue-500">
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <Lock className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="password"
                type="password"
                required
                className="block w-full rounded-xl border-gray-200 bg-gray-50/50 py-2.5 pl-10 pr-3 text-sm outline-none transition-all focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100 placeholder:text-gray-400"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center rounded-xl bg-gray-900 py-2.5 text-sm font-medium text-white transition-all hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-gray-500">
          Don't have an account?{' '}
          <Link to="/register" className="font-semibold text-blue-600 hover:text-blue-500">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
