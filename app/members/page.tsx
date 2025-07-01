"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";

export default function EditMembersPage() {
  const [members, setMembers] = useState<string[]>([]);
  const [newMember, setNewMember] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const fetchData = async () => {
      try {
        await axios.get("/api/auth/check", { withCredentials: true });
        const res = await axios.get("/api/members", { withCredentials: true });
        setMembers(res.data);
      } catch {
        router.push("/");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [router]);

  const handleSave = async () => {
    setError("");
    setSuccess("");
    try {
      await axios.post(
        "/api/members",
        { members },
        { withCredentials: true }
      );
      setSuccess("팀원 수정이 완료되었습니다!");
    } catch (err) {
      setError("팀원 저장에 실패했어요.");
    }
  };

  const addMember = () => {
    if (!newMember.trim()) return;
    setMembers((prev) => [...prev, newMember.trim()]);
    setNewMember("");
  };

  const removeMember = (name: string) => {
    setMembers((prev) => prev.filter((m) => m !== name));
  };

  if (loading) return null;

  return (
    <div className="p-6 max-w-xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">팀원 관리자</h1>
        <button
          className="text-sm text-blue-600 underline"
          onClick={() => router.push("/")}
        >
          돌아가기
        </button>
      </div>

      <div className="flex space-x-2 mb-4">
        <input
          type="text"
          className="border p-2 w-full"
          placeholder="팀원 이름 입력"
          value={newMember}
          onChange={(e) => setNewMember(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addMember();
          }}
        />
        <button className="bg-green-600 text-white px-4" onClick={addMember}>
          +
        </button>
      </div>

      <ul className="mb-4">
        {members.map((name) => (
          <li
            key={name}
            className="flex justify-between items-center border p-2 mb-2"
          >
            <span>{name}</span>
            <button
              className="text-red-600 text-sm"
              onClick={() => removeMember(name)}
            >
              삭제
            </button>
          </li>
        ))}
      </ul>

      <button
        className="bg-blue-600 text-white px-4 py-2"
        onClick={handleSave}
      >
        Save
      </button>

      {error && <p className="text-red-600 mt-4">{error}</p>}
      {success && <p className="text-green-600 mt-4">{success}</p>}
    </div>
  );
}
