import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Settings, LogOut, MessageSquare } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Chat() {
  const [messages, setMessages] = useState([
    { id: 1, role: 'assistant', text: 'Hello! I am your AI assistant. How can I help you today?', time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }
  ]);
  const [input, setInput] = useState('');
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);

  const activeConversationRef = useRef(currentConversationId);
  const draftIdRef = useRef(Date.now()); // Tracks the exact instance of a "New Chat"

  useEffect(() => {
    activeConversationRef.current = currentConversationId;
  }, [currentConversationId]);

  const fetchConversations = async (token) => {
    try {
      const res = await fetch('/api/conversations', {
        headers: { 'Authorization': `Bearer ${token}` },
        cache: 'no-store'
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (e) { console.error(e); }
  };

  const selectConversation = async (id) => {
    const token = localStorage.getItem('token');
    if (!token) return;
    setIsLoading(true);
    try {
      const res = await fetch(`/api/conversations/${id}/messages`, {
        headers: { 'Authorization': `Bearer ${token}` },
        cache: 'no-store'
      });
      if (res.ok) {
        const data = await res.json();
        const formatted = data.map(msg => {
          let parsedSources = [];
          if (typeof msg.sources === 'string') {
            try { parsedSources = JSON.parse(msg.sources); } catch (e) {}
          } else if (Array.isArray(msg.sources)) {
            parsedSources = msg.sources;
          }
          
          return {
            id: msg.id,
            role: msg.role,
            text: msg.content,
            time: msg.time_str || (msg.created_at ? new Date(msg.created_at).toLocaleString([], {month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute:'2-digit'}) : 'Unknown Time'),
            sources: parsedSources.map(s => ({
              name: s.document_name || s.name || 'Unknown',
              url: s.document_sharepoint_url || s.url || null
            }))
          };
        });
        setMessages(formatted);
        setCurrentConversationId(id);
      }
    } catch (e) { console.error(e); }
    finally { setIsLoading(false); }
  };

  const startNewChat = () => {
    setCurrentConversationId(null);
    draftIdRef.current = Date.now();
    setMessages([{ id: Date.now(), role: 'assistant', text: 'Hello! I am your AI assistant. How can I help you today?', time: new Date().toLocaleString([], {month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute:'2-digit'}) }]);
  };

  // Check token on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
    } else {
      fetchConversations(token);
    }
  }, [navigate]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (input === '' && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const handleChange = (e) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const handleSend = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!input.trim() || isLoading) return;

    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    const newUserMsg = {
      id: Date.now(),
      role: 'user',
      text: input,
      time: new Date().toLocaleString([], {month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute:'2-digit'})
    };
    
    const updatedMessages = [...messages, newUserMsg];
    setMessages(updatedMessages);
    setInput('');
    setIsLoading(true);

    try {
      let activeConvId = currentConversationId;
      if (!activeConvId) {
         const userQuery = newUserMsg.text.trim();
         const titleStr = userQuery.length > 30 ? userQuery.substring(0, 30) + '...' : userQuery;
         const convRes = await fetch('/api/conversations', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ title: titleStr })
         });
         
         if (convRes.ok) {
            const convData = await convRes.json();
            activeConvId = convData.id;
            setCurrentConversationId(activeConvId);
            fetchConversations(token);
         }
      }

      const apiMessages = updatedMessages.map(m => ({
        role: m.role,
        content: m.text,
        time: m.time
      }));

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ messages: apiMessages, conversation_id: activeConvId })
      });

      if (res.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
        return;
      }
      
      const data = await res.json();
      
      const sources = data.artifact?.map(doc => ({
        name: doc.document_name || 'Unknown',
        url: doc.document_sharepoint_url || null
      })) || [];

      const newAiMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        text: data.content || data.error || 'Sorry, no response generated.',
        time: data.time_str || new Date().toLocaleString([], {month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute:'2-digit'}),
        sources: sources
      };
      
      let targetConvId = activeConvId;
      const originalDraftId = draftIdRef.current;

      const isStillViewingTarget = targetConvId 
        ? (activeConversationRef.current === targetConvId)
        : (activeConversationRef.current === null && draftIdRef.current === originalDraftId);

      if (isStillViewingTarget) {
        setMessages(prev => [...prev, newAiMsg]);
      }

      if (data.conversation_id) {
        fetchConversations(token);
      }
    } catch (err) {
      const matchTarget = activeConvId ? (activeConversationRef.current === activeConvId) : (activeConversationRef.current === null && draftIdRef.current === draftIdRef.current);
      if (matchTarget) {
        const errorMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          text: 'Sorry, I encountered an error connecting to the server.',
          time: new Date().toLocaleString([], {month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute:'2-digit'})
        };
        setMessages(prev => [...prev, errorMsg]);
      }
    } finally {
      const matchTarget = activeConvId ? (activeConversationRef.current === activeConvId) : (activeConversationRef.current === null && draftIdRef.current === draftIdRef.current);
      if (matchTarget) {
        setIsLoading(false);
      }
    }
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar - Desktop Only */}
      <div className="hidden w-80 flex-col border-r border-gray-100 bg-gray-50/30 lg:flex">
        <div className="flex h-16 items-center justify-between border-b border-gray-100 px-6 shrink-0">
          <div className="flex items-center gap-2 font-semibold text-gray-900">
            <Bot className="h-6 w-6 text-blue-600" />
            <span>AI Assistant</span>
          </div>
        </div>
        
        <div className="px-4 py-3 border-b border-gray-100 shrink-0">
          <button onClick={startNewChat} className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors">
            <MessageSquare className="h-4 w-4" />
            New Chat
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto py-4">
          <div className="px-4 text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">Recent Chats</div>
          <div className="space-y-1 px-3">
            {conversations.map((conv) => (
              <button 
                key={conv.id} 
                onClick={() => selectConversation(conv.id)}
                className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all focus:outline-none ${currentConversationId === conv.id ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-white hover:shadow-sm'}`}
              >
                <MessageSquare className={`h-4 w-4 shrink-0 ${currentConversationId === conv.id ? 'text-blue-500' : 'text-gray-400 group-hover:text-blue-500'}`} />
                <div className="truncate text-left font-medium">{conv.title || 'Conversation'}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-gray-100 p-4">
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

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Mobile Header overlay for smaller screens, simple nav for desktop */}
        <div className="flex h-16 items-center border-b border-gray-100 bg-white px-6 shadow-sm z-10">
           <h1 className="text-lg font-medium text-gray-900">Current Conversation</h1>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto bg-gray-50/50 p-6 scroll-smooth">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${msg.role === 'user' ? 'bg-gray-900 text-white' : 'bg-blue-600 text-white'}`}>
                  {msg.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </div>
                <div className={`flex max-w-[80%] flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`rounded-2xl px-5 py-2.5 text-[15px] leading-relaxed shadow-sm ${
                    msg.role === 'user' 
                      ? 'bg-gray-900 text-white rounded-tr-sm' 
                      : 'bg-white text-gray-800 ring-1 ring-gray-100 rounded-tl-sm'
                  }`}>
                    <div className="whitespace-pre-wrap">{msg.text}</div>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 border-t border-gray-100 pt-3">
                        <div className="text-[11px] font-semibold text-gray-500 mb-1.5 flex items-center uppercase tracking-wider">
                          Sources
                        </div>
                        <ul className="space-y-1 pl-4 list-disc marker:text-gray-300">
                          {msg.sources.map((src, i) => (
                            <li key={i} className="text-sm text-gray-600">
                              {src.url ? (
                                <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-700 hover:underline">
                                  {src.name}
                                </a>
                              ) : (
                                src.name
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                  <span className="mt-1.5 text-xs font-medium text-gray-400 px-1">{msg.time}</span>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-100 bg-white p-4">
          <div className="mx-auto max-w-3xl">
            <form onSubmit={handleSend} className="relative flex items-end gap-2">
              <div className="relative flex-1">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleChange}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a message..."
                  rows={1}
                  className="block w-full overflow-hidden resize-none rounded-2xl border-gray-200 bg-gray-50 py-3.5 pl-5 pr-12 text-[15px] leading-[24px] outline-none transition-all placeholder:text-gray-400 focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100"
                  style={{ minHeight: '52px', maxHeight: '200px' }}
                />
              </div>
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white transition-all hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 active:scale-95"
              >
                {isLoading ? (
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </button>
            </form>
            
          </div>
        </div>
      </div>
    </div>
  );
}
