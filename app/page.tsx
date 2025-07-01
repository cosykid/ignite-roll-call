"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";
import Link from "next/link";
import { QRCodeCanvas } from "qrcode.react";

// ✅ Inline QR component
function QRImage({ value }: { value: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [imgSrc, setImgSrc] = useState<string | null>(null);

  useEffect(() => {
    if (canvasRef.current) {
      const dataUrl = canvasRef.current.toDataURL("image/png");
      setImgSrc(dataUrl);
    }
  }, []);

  return (
    <>
      <div style={{ display: "none" }}>
        <QRCodeCanvas value={value} size={256} ref={canvasRef} />
      </div>
      {imgSrc && <img src={imgSrc} alt="QR Code" width={256} height={256} />}
    </>
  );
}

export default function Home() {
  const [password, setPassword] = useState("");
  const [session, setSession] = useState<any | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  // ✅ On mount: check authentication first
  useEffect(() => {
    const checkAuthAndLoadSession = async () => {
      try {
        await axios.get("/api/auth/check", { withCredentials: true });
        setAuthenticated(true);
        // If authenticated, load the session data
        const res = await axios.get("/api/session", { withCredentials: true });
        setSession(res.data);
      } catch (err) {
        setAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };

    checkAuthAndLoadSession();
  }, []);

  const handleLogin = async () => {
    try {
      await axios.post(
        "/api/login",
        { password },
        { withCredentials: true }
      );
      // After login, re-check authentication and load session
      const resAuth = await axios.get("/api/auth/check", { withCredentials: true });
      if (resAuth.status === 200) {
        setAuthenticated(true);
        const resSession = await axios.get("/api/session", { withCredentials: true });
        setSession(resSession.data);
      }
    } catch (err) {
      alert("Incorrect password.");
      setAuthenticated(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleLogin();
  };

  if (loading) return null;

  return (
    <div className="p-4 max-w-xl mx-auto">
      {!authenticated ? (
        <div>
          <h2 className="text-xl font-bold mb-2">Enter Admin Password</h2>
          <input
            className="border p-2 w-full mb-2"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            onClick={handleLogin}
            className="bg-blue-600 text-white px-4 py-2"
          >
            Login
          </button>
        </div>
      ) : (
        <div>
          <h1 className="text-2xl font-bold mb-4">이그나이트 예배팀 출석체크</h1>
          <div className="flex flex-row gap-4 mb-4">
            <Link href="/members" className="text-blue-600 underline">
              팀원 추가/삭제
            </Link>
            <Link href="/edit" className="text-blue-600 underline">
              예배 시간 수정
            </Link>
          </div>

          {session ? (
            <div className="border p-4 rounded">
              <div>
                {new Date(session.datetime).toLocaleString("ko-KR", {
                  dateStyle: "full",
                  timeStyle: "short",
                })}
              </div>
              <div className="mt-2">
                <Link href="/remove" className="text-blue-600 underline">
                  이번주 예배 명단 수정하기
                </Link>
                {session.members.length > 0 ? (
                  <div>{session.members.join(", ")}</div>
                ) : (
                  <div>전원 정시에 도착</div>
                )}
              </div>
              <div className="mt-2">
                <Link href="/register">
                  <span className="text-blue-600 underline">
                    QR 링크
                  </span>
                </Link>
              </div>
              <div className="mt-2">
                <QRImage value={`${window.location.origin}/register`} />
              </div>
            </div>
          ) : (
            <p>활성 세션이 없습니다.</p>
          )}
        </div>
      )}
    </div>
  );
}
