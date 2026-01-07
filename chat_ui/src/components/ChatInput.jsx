import React, { useState, useRef, useEffect } from 'react';
// import { Send, Paperclip, Image, Mic, Sparkles, StopCircle } from 'lucide-react'; // Removed lucide-react

const ChatInput = ({ onSendMessage, isGenerating }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);

  // 텍스트 입력 높이 자동 조절
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isGenerating) return;
    onSendMessage(input);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-6 pt-2">
      <div className="relative bg-white rounded-2xl border border-gray-200 shadow-xl focus-within:ring-2 focus-within:ring-blue-500/50 transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="RAG AI에게 무엇이든 물어보세요..."
          className="w-full bg-transparent text-gray-900 placeholder-gray-400 p-4 pr-12 rounded-2xl resize-none focus:outline-none min-h-[56px] max-h-[200px] overflow-y-auto scrollbar-thin"
          rows={1}
        />

        {/* 입력창 하단 툴바 */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          <div className="flex items-center gap-2">
            <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors" title="파일 첨부">
              <i className="fas fa-paperclip text-lg"></i>
            </button>
            <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors" title="이미지 업로드">
              <i className="far fa-image text-lg"></i>
            </button>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!input.trim() && !isGenerating}
            className={`p-2 rounded-lg transition-all duration-200 ${isGenerating
              ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse'
              : input.trim()
                ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
          >
            {isGenerating ? <i className="fas fa-circle-stop text-lg"></i> : <i className="fas fa-paper-plane text-lg"></i>}
          </button>
        </div>
      </div>

      <div className="text-center mt-2">
        <p className="text-xs text-gray-500">
          AI는 실수할 수 있습니다. 중요한 정보는 확인이 필요합니다.
        </p>
      </div>
    </div>
  );
};

export default ChatInput;
