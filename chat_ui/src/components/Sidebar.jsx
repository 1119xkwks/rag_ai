import React from 'react';
import { Plus, MessageSquare, Settings, LogOut, X, Database, Search, Boxes } from 'lucide-react';

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
        className={`fixed md:relative z-30 w-[260px] h-full flex flex-col bg-gray-900 border-r border-gray-800 transform transition-transform duration-300 ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
          }`}
      >
        <div className="p-3">
          {/* 닫기 버튼 (모바일 전용) */}
          <button
            onClick={onClose}
            className="md:hidden absolute top-4 right-[-40px] p-2 text-gray-400 hover:text-white"
          >
            <X size={24} />
          </button>

          {/* 새 채팅 버튼 */}
          <button
            onClick={onNewChat}
            className="flex items-center gap-3 w-full px-4 py-3 mb-4 text-sm text-left text-white bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors shadow-sm"
          >
            <Plus size={18} />
            <span className="font-semibold">New Chat</span>
          </button>

          {/* 메뉴 섹션 */}
          <div className="flex flex-col gap-1 mb-6">
            <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
              Platform
            </div>
            <button className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 rounded-md transition-colors">
              <Search size={16} />
              Search Engine
            </button>
            <button className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 rounded-md transition-colors">
              <Database size={16} />
              Knowledge Base
            </button>
            <button className="flex items-center gap-3 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 rounded-md transition-colors">
              <Boxes size={16} />
              Agents
            </button>
          </div>
        </div>

        {/* 채팅 히스토리 영역 */}
        <div className="flex-1 overflow-y-auto px-3 py-2 scrollbar-thin scrollbar-thumb-gray-700">
          <div className="mb-2 px-2 text-xs font-semibold text-gray-500">Recent</div>
          {history.map((item) => (
            <button
              key={item.id}
              className="flex items-center gap-3 w-full px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 rounded-md group transition-colors truncate"
            >
              <MessageSquare size={16} className="text-gray-500 group-hover:text-gray-300 shrink-0" />
              <span className="truncate">{item.title}</span>
            </button>
          ))}
        </div>

        {/* 하단 사용자/설정 영역 */}
        <div className="p-3 border-t border-gray-800">
          <button className="flex items-center gap-3 w-full px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 rounded-md transition-colors">
            <Settings size={18} />
            <span>Settings</span>
          </button>
          <button className="flex items-center gap-3 w-full px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 rounded-md transition-colors mt-1">
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
