import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { password } = await request.json();
    const correctPassword = process.env.ADMIN_PASSWORD;

    if (!correctPassword) {
      console.error('[auth] ADMIN_PASSWORD not set in environment variables');
      return NextResponse.json(
        { success: false, message: 'サーバー設定エラー' },
        { status: 500 }
      );
    }

    if (password === correctPassword) {
      return NextResponse.json({ success: true });
    } else {
      return NextResponse.json(
        { success: false, message: 'パスワードが間違っています' },
        { status: 401 }
      );
    }
  } catch {
    return NextResponse.json(
      { success: false, message: '認証処理でエラーが発生しました' },
      { status: 500 }
    );
  }
}
