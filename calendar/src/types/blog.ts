export type BlogImage = {
  url: string;
  height: number;
  width: number;
};

export type BlogPost = {
  id: string;
  createdAt: string;
  updatedAt: string;
  publishedAt: string;
  revisedAt: string;
  title: string;
  content: string;
  eyecatch?: BlogImage;
};

export type BlogResponse = {
  contents: BlogPost[];
  totalCount: number;
  offset: number;
  limit: number;
};
