import React from 'react';
import { User, Sparkles, Copy, ThumbsUp, ThumbsDown, RotateCw, FileText, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`group w-full max-w-3xl mx-auto px-4 py-6 flex gap-4 md:gap-6 ${isUser ? '' : 'bg-gray-900/50'}`}>
      {/* 아바타 영역 */}
      <div className="flex-shrink-0 flex flex-col items-center">
        {isUser ? (
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-lg">
            <User size={18} />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-green-400 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-900/20 ring-1 ring-white/10">
            <Sparkles size={16} />
          </div>
        )}
      </div>

      {/* 메시지 내용 영역 */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* 이름 */}
        <div className="font-semibold text-sm text-gray-200">
          {isUser ? 'You' : 'RAG Assistant'}
        </div>

        {/* 텍스트 내용 */}
        <div className={`prose prose-invert prose-p:leading-relaxed prose-pre:bg-gray-800 max-w-none text-gray-100 ${isUser ? 'whitespace-pre-wrap' : ''}`}>
          {/* 마크다운 렌더링 흉내, 실제로는 dangerouslySetInnerHTML 혹은 react-markdown 라이브러리 필요하지만 여기선 단순 텍스트 처리 */}
          {message.content.split('\n').map((line, i) => (
            <p key={i} className="min-h-[1em] mb-2">{line}</p>
          ))}
        </div>

        {/* AI 응답일 경우 추가 UI (소스, 피드백 등) */}
        {!isUser && (
          <div className="pt-2 flex flex-col gap-3">
            {/* 출처 표시 (Dummy) */}
            {message.sources && message.sources.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {message.sources.map((src, idx) => (
                  <button key={idx} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs text-blue-300 transition-colors">
                    <FileText size={12} />
                    <span className="truncate max-w-[150px]">{src}</span>
                  </button>
                ))}
              </div>
            )}

            {/* 추천 질문 (Follow-up) */}
            {message.suggestions && (
              <div className="flex flex-col gap-1.5 mt-1">
                <span className="text-xs text-gray-500 font-medium ml-1">관련 질문</span>
                {message.suggestions.map((sugg, idx) => (
                  <button key={idx} className="flex items-center justify-between w-full md:w-auto text-left px-4 py-2 bg-gray-800/50 hover:bg-gray-800 border-l-2 border-blue-500 rounded-r-lg text-sm text-gray-300 transition-colors group/btn">
                    <span>{sugg}</span>
                    <ChevronRight size={14} className="opacity-0 group-hover/btn:opacity-100 transition-opacity text-blue-400" />
                  </button>
                ))}
              </div>
            )}

            {/* 액션 버튼들 */}
            <div className="flex items-center gap-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded hover:bg-gray-800" title="복사">
                <Copy size={16} />
              </button>
              <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded hover:bg-gray-800" title="다시 생성">
                <RotateCw size={16} />
              </button>
              <div className="h-3 w-px bg-gray-700 mx-1"></div>
              <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded hover:bg-gray-800" title="좋아요">
                <ThumbsUp size={16} />
              </button>
              <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded hover:bg-gray-800" title="싫어요">
                <ThumbsDown size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
