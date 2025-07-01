"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";

export default function RemoveMembersPage() {
  const router = useRouter();

  const [session, setSession] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load active session
  useEffect(() => {
    axios
      .get("/api/session", { withCredentials: true })
      .then((res) => {
        setSession(res.data);
      })
      .catch(() => {
        setError("세션 정보를 불러올 수 없습니다. 로그인 후 다시 시도하세요.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleRemoveMember = async (name: string) => {
    if (!confirm(`${name}님을 이번 세션에서 제거하시겠습니까?`)) return;
    try {
      await axios.delete("/api/session/member", {
        data: { name },
        withCredentials: true,
      });
      // Refresh session
      const res = await axios.get("/api/session", {
        withCredentials: true,
      });
      setSession(res.data);
    } catch (err) {
      alert("멤버 제거에 실패했습니다.");
    }
  };

  if (loading) return <p className="p-4">로딩 중...</p>;
  if (error) return <p className="p-4 text-red-600">{error}</p>;

  return (
    <div className="p-6 max-w-xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">예배 명단</h1>
        <button
          className="text-sm text-blue-600 underline"
          onClick={() => router.push("/")}
        >
          돌아가기
        </button>
      </div>

      <div className="mb-4">
        <div className="text-gray-700">
          {new Date(session.datetime).toLocaleString("ko-KR", {
            dateStyle: "full",
            timeStyle: "short",
          })}
          {" "}예배
        </div>
      </div>

      {session.members.length > 0 ? (
        <ul className="space-y-2">
          {session.members.map((name: string) => (
            <li
              key={name}
              className="flex justify-between items-center border p-2 rounded"
            >
              <span>{name}</span>
              <button
                className="text-red-600 text-sm"
                onClick={() => handleRemoveMember(name)}
              >
                제거
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-green-700">전원 정시에 도착했습니다!</p>
      )}
    </div>
  );
}
