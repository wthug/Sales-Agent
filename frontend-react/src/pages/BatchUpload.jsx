import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Download, Bot, MessageSquare, LogOut, ChevronDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const FOLDER_OPTIONS = ['AML', 'ALM', 'FM'];

export default function BatchUpload() {
  const [file, setFile] = useState(null);
  const [folderName, setFolderName] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [status, setStatus] = useState('IDLE');
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState({ message: '', current: 0, total: 1 });
  const [history, setHistory] = useState([]);
  const fileInputRef = useRef(null);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  // Handle click outside dropdown
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    
    fetchHistory();
    
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchHistory = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/batch_history', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (e) {
      console.error('Failed to fetch history', e);
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected && selected.name.endsWith('.csv')) {
      setFile(selected);
      setError(null);
    } else {
      setFile(null);
      setError('Please select a valid .csv file.');
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!folderName) {
      setError('Please select a domain before uploading.');
      return;
    }

    setStatus('PROCESSING');
    setError(null);
    setProgress({ message: 'Processing your file... This may take a while.', current: 0, total: 1 });

    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder_name', folderName);

    // Optimistic UI update
    const pendingRow = {
      task_id: 'pending-' + Date.now(),
      input_filename: file.name,
      output_filename: `output_${file.name.split('.')[0]}.xlsx`,
      status: 'pending',
      created_at: new Date().toISOString()
    };
    setHistory(prev => [pendingRow, ...prev]);

    try {
      const res = await fetch('/api/batch_upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      
      const data = await res.json().catch(() => ({}));
      
      if (res.ok && data.success) {
        setStatus('SUCCESS');
        fetchHistory(); // Refresh to get the real task_id and status
      } else {
        setStatus('ERROR');
        setError(data.error || 'Failed to process batch.');
        fetchHistory(); // Refresh to update the failed status
      }
    } catch (err) {
      setStatus('ERROR');
      setError('Network error occurred during upload.');
      fetchHistory(); // Refresh to update the failed status
    }
  };

  const handleFetchFile = async (taskId, outputFilename) => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/batch_download_file/${taskId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = outputFilename || 'results.xlsx';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      } else {
        console.error('Failed to download file');
      }
    } catch (err) {
      console.error('Download error:', err);
    }
  };

  const handleReset = () => {
    setFile(null);
    if (downloadUrl) {
        window.URL.revokeObjectURL(downloadUrl);
        setDownloadUrl(null);
    }
    setStatus('IDLE');
    setProgress({ message: '', current: 0, total: 1 });
    setError(null);
    setFolderName('');
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar */}
      <div className="hidden w-80 flex-col border-r border-gray-100 bg-gray-50/30 lg:flex">
        <div className="flex h-16 items-center justify-between border-b border-gray-100 px-6 shrink-0">
          <div className="flex items-center gap-2 font-semibold text-gray-900">
            <Bot className="h-6 w-6 text-blue-600" />
            <span>AI Assistant</span>
          </div>
        </div>

        <div className="px-4 py-3 border-b border-gray-100 shrink-0 space-y-3">
          <button className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 py-2.5 text-sm font-medium text-white cursor-default">
            <FileText className="h-4 w-4" />
            Batch Processing
          </button>
          <button onClick={() => navigate('/chat')} className="w-full flex items-center justify-center gap-2 rounded-xl bg-white border border-gray-200 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
            <MessageSquare className="h-4 w-4" />
            Back to Chat
          </button>
        </div>

        <div className="border-t border-gray-100 p-4 mt-auto">
          <div className="flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm ring-1 ring-gray-100">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-700 font-semibold uppercase">
              {localStorage.getItem('username')?.substring(0, 2) || 'U'}
            </div>
            <div className="flex-1 overflow-hidden">
              <div className="truncate text-sm font-medium text-gray-900">{localStorage.getItem('username') || 'User'}</div>
            </div>
            <button onClick={() => {
              localStorage.removeItem('token');
              localStorage.removeItem('username');
              navigate('/login');
            }} className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-900 transition-colors" title="Log Out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-y-auto bg-gray-50/50 p-8">
        <div className="mx-auto w-full max-w-3xl space-y-8">

          {/* Header row */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Matrix Batch Processing</h1>
              <p className="text-gray-500 mt-1 text-sm">
                Upload a .csv file with <span className="font-medium text-gray-700">Item</span> and <span className="font-medium text-gray-700">Specification</span> columns.
                The AI agent will process each row and return a CSV with responses.
              </p>
            </div>

            {/* Folder dropdown */}
            <div className="relative shrink-0" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setDropdownOpen(o => !o)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl border border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 shadow-sm transition-colors min-w-[130px] justify-between"
              >
                <span>{folderName || 'Select Domain'}</span>
                <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-44 bg-white rounded-xl shadow-lg ring-1 ring-gray-100 z-50 overflow-hidden">
                  {FOLDER_OPTIONS.map(opt => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => { setFolderName(opt); setDropdownOpen(false); }}
                      className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                        folderName === opt
                          ? 'bg-blue-50 text-blue-700 font-medium'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Upload card */}
          <div className="bg-white rounded-2xl shadow-sm ring-1 ring-gray-100 p-8">
            <div className={`border-2 border-dashed rounded-xl p-10 text-center transition-colors ${file ? 'border-blue-400 bg-blue-50/50' : 'border-gray-200 hover:border-gray-300'}`}>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".csv"
                className="hidden"
              />

              {!file ? (
                <div className="flex flex-col items-center cursor-pointer" onClick={() => fileInputRef.current?.click()}>
                  <div className="h-14 w-14 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                    <Upload className="h-6 w-6 text-gray-500" />
                  </div>
                  <h3 className="text-sm font-medium text-gray-900 mb-1">Click to upload document</h3>
                  <p className="text-xs text-gray-500">Supported formats: .csv</p>
                  {folderName && (
                    <span className="mt-3 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-600 border border-blue-100">
                      Folder: {folderName}
                    </span>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <div className="h-14 w-14 bg-blue-100 rounded-full flex items-center justify-center mb-4">
                    <FileText className="h-6 w-6 text-blue-600" />
                  </div>
                  <h3 className="text-sm font-medium text-gray-900 mb-1">{file.name}</h3>
                  <p className="text-xs text-gray-500 mb-1">{(file.size / 1024).toFixed(2)} KB</p>
                  {folderName && (
                    <span className="mb-4 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-600 border border-blue-100">
                      Folder: {folderName}
                    </span>
                  )}

                  {status === 'IDLE' && (
                    <div className="flex gap-3 mt-2">
                      <button onClick={handleReset} className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                        Cancel
                      </button>
                      <button onClick={handleUpload} className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors">
                        Start Processing
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="mt-6 flex items-center gap-3 p-4 text-red-700 bg-red-50 rounded-xl">
                <AlertCircle className="h-5 w-5 shrink-0" />
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}

            {/* Progress */}
            {(status === 'UPLOADING' || status === 'PROCESSING') && (
              <div className="mt-8 space-y-4">
                <div className="flex items-center justify-between text-sm font-medium">
                  <span className="text-gray-900">{progress.message || 'Initializing...'}</span>
                  <span className="text-blue-600">
                    {progress.total > 1 ? Math.round((progress.current / progress.total) * 100) : 0}%
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `100%` }}
                  />
                </div>
              </div>
            )}

            {/* Success */}
            {status === 'SUCCESS' && (
              <div className="mt-8 flex flex-col items-center justify-center p-6 bg-green-50 rounded-xl border border-green-100 text-center">
                <CheckCircle className="h-10 w-10 text-green-500 mb-3" />
                <h3 className="text-lg font-medium text-gray-900 mb-1">Processing Complete!</h3>
                <p className="text-sm text-gray-600 mb-5">Your file has been fully processed by the AI agent.</p>
                <div className="flex gap-3">
                  <button
                    onClick={handleReset}
                    className="px-5 py-2.5 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Process Another File
                  </button>
                </div>
              </div>
            )}
          </div>
          
          {/* History Table */}
          <div className="bg-white rounded-2xl shadow-sm ring-1 ring-gray-100 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h2 className="text-lg font-medium text-gray-900">Batch Processing History</h2>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-100">
                <thead className="bg-gray-50/80 sticky top-0 backdrop-blur-sm">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Input File</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Output File</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-50">
                  {history.map((row) => (
                    <tr key={row.task_id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                        {row.input_filename}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {row.output_filename}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(row.created_at).toLocaleDateString()} {new Date(row.created_at).toLocaleTimeString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          row.status === 'successful' ? 'bg-green-100 text-green-800 border border-green-200' :
                          row.status === 'failed' ? 'bg-red-100 text-red-800 border border-red-200' :
                          'bg-yellow-100 text-yellow-800 border border-yellow-200'
                        }`}>
                          {row.status.charAt(0).toUpperCase() + row.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        {row.status === 'successful' && (
                          <button
                            onClick={() => handleFetchFile(row.task_id, row.output_filename)}
                            className="inline-flex items-center gap-1.5 text-blue-600 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors"
                          >
                            <Download className="h-4 w-4" />
                            Fetch
                          </button>
                        )}
                        {row.status === 'pending' && (
                          <span className="text-gray-400 text-sm italic">Processing...</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {history.length === 0 && (
                    <tr>
                      <td colSpan="5" className="px-6 py-8 text-center text-sm text-gray-500">
                        No processing history found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
