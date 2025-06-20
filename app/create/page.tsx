"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";

export default function CreateSessionPage() {
  const router = useRouter();
  const [teamMembers, setTeamMembers] = useState<string[]>([]);
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    axios
      .get("/api/members", { withCredentials: true })
      .then((res) => {
        setTeamMembers(res.data);
      })
      .catch(() => {
        router.push("/"); // ⬅ Redirect to root on auth failure
      });
  }, []);
  const toggleMember = (name: string) => {
    setSelectedMembers((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name]
    );
  };

  const handleSubmit = async () => {
    if (!date || !time || selectedMembers.length === 0) {
      setError("All fields are required.");
      return;
    }

    try {
      // Construct datetime string and parse as Sydney time
      const localDateTime = new Date(`${date}T${time}`);
      const sydneyOffset = 10 * 60 + (new Date().getTimezoneOffset()); // Adjust from local to Sydney
      localDateTime.setMinutes(localDateTime.getMinutes() + sydneyOffset);
      
      await axios.post(
        "/api/session",
        {
          date, // e.g. "2025-06-21"
          time, // e.g. "12:30"
          members: selectedMembers,
        },
        { withCredentials: true }
      );


      router.push("/");
    } catch (err) {
      setError("Failed to create session.");
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">새 일정</h1>
        <button
          className="text-sm text-blue-600 underline"
          onClick={() => router.push("/")}
        >
          돌아가기
        </button>
      </div>

      <div className="px-4 py-6 max-w-xl w-full mx-auto overflow-x-hidden">
        <label className="block mb-2 text-sm">날짜 선택*</label>
        <input
          type="date"
          className="border p-3 text-lg w-full max-w-full mb-4 rounded"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />

        <label className="block mb-2 text-sm">시간 선택*</label>
        <input
          type="time"
          className="border p-3 text-lg w-full max-w-full mb-4 rounded"
          value={time}
          onChange={(e) => setTime(e.target.value)}
        />
      </div>

      <label className="block mb-2 text-sm">라인업 선택*</label>
      <div className="mb-4 space-y-2">
        {teamMembers.map((name) => (
          <label
            key={name}
            className="flex items-center justify-between border rounded-lg px-4 py-2 cursor-pointer"
          >
            <span>{name}</span>
            <input
              type="checkbox"
              checked={selectedMembers.includes(name)}
              onChange={() => toggleMember(name)}
              className="w-5 h-5"
            />
          </label>
        ))}
      </div>

      <button
        className="bg-blue-600 text-white px-4 py-3 w-full text-lg rounded"
        onClick={handleSubmit}
      >
        세 일정 생성
      </button>

      {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}
      {success && <p className="text-green-600 mt-4 text-sm">{success}</p>}
    </div>
  );
}
