import React from 'react';
// import { Plus, MessageSquare, Settings, LogOut, X, Database, Search, Boxes } from 'lucide-react'; // Removed lucide-react

const Sidebar = ({ isOpen, onClose, onNewChat }) => {
  // 더미 채팅 히스토리 데이터
  const history = [
    { id: 1, title: 'RAG 파이프라인 설계' },
    { id: 2, title: '벡터 DB 성능 최적화' },
    { id: 3, title: '오픈소스 LLM 비교' },
    { id: 4, title: '리액트 컴포넌트 구조' },
    { id: 5, title: '파이썬 비동기 처리' },
  ];

  return (
    <>
      {/* 모바일 오버레이 */}
      <div
        className={`fixed inset-0 bg-black/50 z-20 md:hidden transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
          }`}
        onClick={onClose}
      />

      {/* 사이드바 본문 */}
      <aside
        className={`fixed md:relative z-30 w-[260px] h-full flex flex-col bg-gray-50 border-r border-gray-200 transform transition-transform duration-300 ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
          }`}
      >
        <div className="p-3">
          {/* 닫기 버튼 (모바일 전용) */}
          <button
            onClick={onClose}
            className="md:hidden absolute top-4 right-[-40px] p-2 text-gray-500 hover:text-white"
          >
            <i className="fas fa-xmark text-2xl"></i>
          </button>

          {/* 새 채팅 버튼 */}
          <button
            onClick={onNewChat}
            className="flex items-center gap-3 w-full px-4 py-3 mb-4 text-sm text-left text-gray-900 bg-white hover:bg-gray-100 border border-gray-200 rounded-lg transition-colors shadow-sm"
          >
            <i className="fas fa-plus text-lg"></i>
            <span className="font-semibold">New Chat</span>
          </button>

          {/* 메뉴 섹션 */}
          <div className="flex flex-col gap-1 mb-6">
            <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
              Platform
            </div>
            <button className="flex items-center gap-3 px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 rounded-md transition-colors">
              <i className="fas fa-magnifying-glass text-gray-500"></i>
              Search Engine
            </button>
            <button className="flex items-center gap-3 px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 rounded-md transition-colors">
              <i className="fas fa-database text-gray-500"></i>
              Knowledge Base
            </button>
            <button className="flex items-center gap-3 px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 rounded-md transition-colors">
              <i className="fas fa-boxes-stacked text-gray-500"></i>
              Agents
            </button>
          </div>
        </div>

        {/* 채팅 히스토리 영역 */}
        <div className="flex-1 overflow-y-auto px-3 py-2 scrollbar-thin scrollbar-thumb-gray-300">
          <div className="mb-2 px-2 text-xs font-semibold text-gray-500">Recent</div>
          {history.map((item) => (
            <button
              key={item.id}
              className="flex items-center gap-3 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 rounded-md group transition-colors truncate"
            >
              <i className="far fa-message text-gray-400 group-hover:text-gray-600 shrink-0"></i>
              <span className="truncate">{item.title}</span>
            </button>
          ))}
        </div>

        {/* 하단 사용자/설정 영역 */}
        <div className="p-3 border-t border-gray-200">
          <button className="flex items-center gap-3 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 rounded-md transition-colors">
            <i className="fas fa-gear text-lg"></i>
            <span>Settings</span>
          </button>
          <button className="flex items-center gap-3 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-200 rounded-md transition-colors mt-1">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-purple-500 to-blue-500 flex items-center justify-center text-[10px] font-bold text-white">
              JS
            </div>
            <div className="flex flex-col items-start">
              <span className="font-medium">User Account</span>
              <span className="text-xs text-gray-500">Free Plan</span>
            </div>
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
