"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";

export default function EditSessionTimePage() {
  const router = useRouter();
  const [time, setTime] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Check auth
  useEffect(() => {
    axios
      .get("/api/auth/check", { withCredentials: true })
      .then(() => {
        setLoading(false);
      })
      .catch(() => {
        router.push("/");
      });
  }, [router]);

  const handleSubmit = async () => {
    if (!time) {
      setError("시간을 입력해주세요.");
      return;
    }
    try {
      await axios.put(
        "/api/default-time",
        { time },
        { withCredentials: true }
      );
      router.push("/");
    } catch (err) {
      console.error(err);
      setError("세션 시간 업데이트에 실패했습니다.");
    }
  };

  if (loading) return null;

  return (
    <div className="p-4 sm:p-6 max-w-xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">예배 시간 수정</h1>
        <button
          className="text-sm text-blue-600 underline"
          onClick={() => router.push("/")}
        >
          돌아가기
        </button>
      </div>

      <label className="block mb-2 text-sm">새 시간*</label>
      <div className="pr-4">
        <input
          type="time"
          className="border p-3 text-lg w-full mb-4 rounded"
          value={time}
          onChange={(e) => setTime(e.target.value)}
        />
      </div>

      <button
        className="bg-blue-600 text-white px-4 py-3 w-full text-lg rounded"
        onClick={handleSubmit}
      >
        시간 업데이트
      </button>

      {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}
      {success && <p className="text-green-600 mt-4 text-sm">{success}</p>}
    </div>
  );
}
