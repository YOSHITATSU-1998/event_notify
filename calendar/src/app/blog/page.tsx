import Link from 'next/link';
import Image from 'next/image';
import { client } from '@/libs/client';
import { BlogResponse } from '@/types/blog';

export const revalidate = 60; // Cache posts for 60 seconds (ISR)

export default async function BlogListPage() {
  let posts: BlogResponse['contents'] = [];
  try {
    const data = await client.get<BlogResponse>({
      endpoint: 'blog',
      queries: { orders: '-publishedAt' },
    });
    posts = data.contents;
  } catch (error) {
    console.error('Failed to fetch blog posts:', error);
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-12">
      {/* ヘッダー */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 py-3 shadow-sm">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Link href="/portal" className="text-gray-500 hover:text-gray-700 text-xs flex items-center gap-1">
            <span>←</span>
            <span>ポータルに戻る</span>
          </Link>
          <h1 className="font-bold text-gray-800 text-sm sm:text-base">運営ドライバーのぼちぼち日記</h1>
          <div className="w-20"></div> {/* Spacer for alignment */}
        </div>
      </header>

      {/* メインコンテンツ */}
      <main className="max-w-2xl mx-auto px-4 mt-6">
        {posts.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border border-gray-100 shadow-sm">
            <span className="text-3xl block mb-2">✍️</span>
            <p className="text-gray-500 text-sm">記事がまだ投稿されていません</p>
            <p className="text-xs text-gray-400 mt-1">microCMSの管理画面から最初の日記を追加してください</p>
          </div>
        ) : (
          <div className="space-y-4">
            {posts.map((post) => {
              const formattedDate = new Date(post.publishedAt || post.createdAt).toLocaleDateString('ja-JP', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
              });

              // Strip HTML tags for clean text preview
              const previewText = post.content
                ? post.content.replace(/<[^>]*>/g, '').substring(0, 100)
                : '';

              return (
                <Link
                  key={post.id}
                  href={`/blog/${post.id}`}
                  className="block bg-white border border-gray-100 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition duration-200"
                >
                  <div className="flex flex-col sm:flex-row">
                    {/* アイキャッチ画像 */}
                    {post.eyecatch ? (
                      <div className="relative w-full sm:w-48 h-36 flex-shrink-0 bg-gray-100">
                        <Image
                          src={post.eyecatch.url}
                          alt={post.title}
                          fill
                          className="object-cover"
                          sizes="(max-width: 640px) 100vw, 192px"
                        />
                      </div>
                    ) : (
                      <div className="relative w-full sm:w-48 h-36 flex-shrink-0 bg-blue-50 flex items-center justify-center text-blue-500 text-2xl font-bold">
                        🚕
                      </div>
                    )}
                    {/* 記事テキスト情報 */}
                    <div className="p-4 flex flex-col justify-between flex-grow">
                      <div>
                        <h2 className="font-bold text-gray-900 text-sm sm:text-base hover:text-blue-600 transition leading-snug line-clamp-2">
                          {post.title}
                        </h2>
                        <p className="text-xs text-gray-500 mt-2 line-clamp-2 leading-relaxed">
                          {previewText}...
                        </p>
                      </div>
                      <div className="text-[10px] text-gray-400 mt-4 flex items-center justify-between">
                        <span>📅 {formattedDate}</span>
                        <span className="text-blue-600 hover:underline">日記を読む →</span>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
