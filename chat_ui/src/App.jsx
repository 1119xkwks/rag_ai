import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInput from './components/ChatInput';
import MessageBubble from './components/MessageBubble';
// import { Menu, Zap } from 'lucide-react'; // Removed lucide-react
import './App.scss'

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      content: '안녕하세요! RAG AI 어시스턴트입니다.\n문서 분석, 데이터 검색, 요약 등 무엇이든 도와드릴 수 있습니다. 어떤 작업을 시작할까요?',
      suggestions: ['PDF 문서 요약해줘', '최근 업로드된 기술 문서 찾아줘']
    }
  ]);
  const messagesEndRef = useRef(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (text) => {
    // 사용자 메시지 추가
    const newUserMsg = { id: Date.now(), role: 'user', content: text };
    setMessages(prev => [...prev, newUserMsg]);
    setIsGenerating(true);

    try {
      // 백엔드 API 호출
      const host = import.meta.env.VITE_SERVER_HOST || 'http://localhost';
      const port = import.meta.env.VITE_SERVER_PORT || '8000';
      const response = await fetch(`${host}:${port}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        throw new Error('Server responded with an error');
      }

      const data = await response.json();

      const newAiMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.answer,
        // 백엔드에서 아직 source를 주지 않으므로 빈 배열 처리 (추후 백엔드 업데이트 필요)
        sources: [],
        suggestions: []
      };
      setMessages(prev => [...prev, newAiMsg]);

    } catch (error) {
      console.error('Chat API Error:', error);
      const errorMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: '죄송합니다. 서버 연결에 실패했거나 오류가 발생했습니다.\n잠시 후 다시 시도해주세요.',
        isError: true
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleNewChat = () => {
    setMessages([
      {
        id: Date.now(),
        role: 'assistant',
        content: '새로운 대화가 시작되었습니다. 무엇을 도와드릴까요?',
      }
    ]);
    setIsSidebarOpen(false); // 모바일에서 닫기
  };

  return (
    <div className="flex h-screen bg-white text-gray-900 font-sans overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onNewChat={handleNewChat}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col relative h-full w-full">
        {/* Top Navigation / Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white/95 backdrop-blur z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 text-gray-600 hover:text-gray-900 rounded-md md:hidden"
            >
              <i className="fas fa-bars text-xl"></i>
            </button>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent">
                RAG AI Service
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">v1.0 Beta</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button className="hidden md:flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-full border border-gray-300 transition-colors">
              <i className="fas fa-bolt text-yellow-500 text-sm"></i>
              <span>GPT-4o</span>
            </button>
          </div>
        </header>

        {/* Chat Area */}
        <main className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent bg-gray-50">
          {messages.length === 0 ? (
            // 빈 화면일 때 (New Chat) - Logo Only
            <div className="h-full flex flex-col items-center justify-center text-gray-500 opacity-50">
              <div className="text-4xl font-bold mb-4">RAG AI</div>
              <p>무엇이든 물어보세요</p>
            </div>
          ) : (
            <div className="flex flex-col pb-4">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} className="h-4" />
            </div>
          )}
        </main>

        {/* Input Area */}
        <div className="bg-gradient-to-t from-gray-50 via-gray-50 to-transparent pt-10 pb-6 px-4">
          <ChatInput onSendMessage={handleSendMessage} isGenerating={isGenerating} />
        </div>
      </div>
    </div>
  )
}

export default App
