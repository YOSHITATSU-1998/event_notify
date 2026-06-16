import Link from 'next/link';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import { client } from '@/libs/client';
import { BlogPost, BlogResponse } from '@/types/blog';

export const revalidate = 60; // Cache post for 60 seconds (ISR)

// Generate static routes during build time for fast page delivery
export async function generateStaticParams() {
  try {
    const data = await client.get<BlogResponse>({
      endpoint: 'blog',
      queries: { limit: 100 },
    });
    return data.contents.map((post) => ({
      id: post.id,
    }));
  } catch (error) {
    console.error('Failed to generate static params:', error);
    return [];
  }
}

type Props = {
  params: Promise<{ id: string }>;
};

export default async function BlogDetailPage({ params }: Props) {
  const { id } = await params;
  let post: BlogPost | null = null;

  try {
    post = await client.get<BlogPost>({
      endpoint: 'blog',
      contentId: id,
    });
  } catch (error) {
    console.error(`Failed to fetch blog post ID: ${id}`, error);
    return notFound();
  }

  if (!post) {
    return notFound();
  }

  const formattedDate = new Date(post.publishedAt || post.createdAt).toLocaleDateString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });

  return (
    <div className="min-h-screen bg-gray-50 pb-16">
      {/* ヘッダー */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 py-3 shadow-sm">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Link href="/blog" className="text-gray-500 hover:text-gray-700 text-xs flex items-center gap-1">
            <span>←</span>
            <span>記事一覧に戻る</span>
          </Link>
          <span className="font-semibold text-gray-400 text-xs">日記詳細</span>
          <div className="w-20"></div> {/* Spacer */}
        </div>
      </header>

      {/* 記事本文 */}
      <main className="max-w-2xl mx-auto px-4 mt-6">
        <article className="bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-sm p-5 sm:p-8">
          {/* 記事メタ情報 */}
          <div className="text-[10px] text-gray-400 mb-2">
            <span>📅 {formattedDate}</span>
          </div>

          {/* 記事タイトル */}
          <h1 className="font-extrabold text-gray-900 text-lg sm:text-2xl leading-snug mb-6">
            {post.title}
          </h1>

          {/* アイキャッチ画像 */}
          {post.eyecatch && (
            <div className="relative w-full h-48 sm:h-72 rounded-xl overflow-hidden mb-8 bg-gray-100">
              <Image
                src={post.eyecatch.url}
                alt={post.title}
                fill
                className="object-cover"
                priority
                sizes="(max-width: 640px) 100vw, 672px"
              />
            </div>
          )}

          {/* note風のブログ本文（Tailwind 4 任意セレクタによる美しいスタイリング） */}
          <div
            className="blog-content border-t border-gray-100 pt-6
              [&_h2]:text-sm [&_h2]:sm:text-base [&_h2]:font-bold [&_h2]:text-gray-900 [&_h2]:mt-8 [&_h2]:mb-4 [&_h2]:border-b [&_h2]:border-gray-200 [&_h2]:pb-2 [&_h2]:flex [&_h2]:items-center [&_h2]:before:content-[''] [&_h2]:before:w-1 [&_h2]:before:h-4 [&_h2]:before:bg-blue-600 [&_h2]:before:mr-2 [&_h2]:before:rounded
              [&_h3]:text-xs [&_h3]:sm:text-sm [&_h3]:font-bold [&_h3]:text-gray-900 [&_h3]:mt-6 [&_h3]:mb-3
              [&_p]:text-xs [&_p]:sm:text-sm [&_p]:text-gray-700 [&_p]:leading-relaxed [&_p]:mb-5
              [&_img]:rounded-xl [&_img]:my-6 [&_img]:max-w-full [&_img]:h-auto [&_img]:mx-auto [&_img]:shadow-sm
              [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-5 [&_ul]:text-xs [&_ul]:sm:text-sm [&_ul]:text-gray-700 [&_ul_li]:mb-1.5
              [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-5 [&_ol]:text-xs [&_ol]:sm:text-sm [&_ol]:text-gray-700 [&_ol_li]:mb-1.5
              [&_a]:text-blue-600 [&_a]:underline [&_a]:font-medium [&_a:hover]:text-blue-800
              [&_strong]:font-bold [&_strong]:text-gray-900
              [&_blockquote]:border-l-4 [&_blockquote]:border-gray-300 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-gray-500 [&_blockquote]:my-6
            "
            dangerouslySetInnerHTML={{ __html: post.content }}
          />
        </article>
      </main>
    </div>
  );
}
