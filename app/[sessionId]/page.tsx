"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import axios from "axios";

export default function SessionCheckin() {
  const params = useParams();
  const sessionId = params?.sessionId;

  const [members, setMembers] = useState<string[]>([]);
  const [selectedName, setSelectedName] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId || typeof sessionId !== "string") return;
    axios
      .get(`/api/${sessionId}`, { withCredentials: true })
      .then((res) => {
        setMembers(res.data.members);
      })
      .catch(() => {
        setStatus("Failed to load session.");
      });
  }, [sessionId]);

  const handleCheckIn = async () => {
    if (!sessionId || typeof sessionId !== "string") return;
    try {
      await axios.post(
        `/api/${sessionId}/remove`,
        {
          name: selectedName,
        },
        { withCredentials: true }
      );
      setStatus("✅ 출석 완료!");
    } catch (err) {
      setStatus("❌ 출석 처리 실패하였습니다");
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <div className="w-full max-w-xl">
        <h1 className="text-2xl font-bold mb-4">이그나이트 예배팀 출석체크</h1>

        <select
          className="border p-2 w-full mb-4"
          value={selectedName}
          onChange={(e) => setSelectedName(e.target.value)}
        >
          <option value="">본인 성함을 선택해주세요</option>
          {members.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>

        <button
          className="bg-green-600 text-white px-4 py-2"
          onClick={handleCheckIn}
          disabled={!selectedName}
        >
          확인
        </button>

        {status && <p className="mt-4 text-center">{status}</p>}
      </div>
    </div>
  );
}
