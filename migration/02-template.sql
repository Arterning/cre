-- 为templates表添加新字段
-- 注意：SQLite的ALTER TABLE ADD COLUMN会将新列添加到表末尾，而不是特定位置
-- 以下语句会将字段添加到表末尾，如需精确控制字段顺序，请使用重建表的方法
ALTER TABLE templates ADD COLUMN api_address TEXT;
ALTER TABLE templates ADD COLUMN login_address TEXT;
ALTER TABLE templates ADD COLUMN redirect_address TEXT;
ALTER TABLE templates ADD COLUMN web_dom TEXT;

ALTER TABLE task_details ADD COLUMN crawl_type TEXT;
ALTER TABLE task_details ADD COLUMN crawl_status TEXT;