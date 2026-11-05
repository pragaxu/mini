-- Run order: 1) this file top to bottom  2) (LOAD DATA needs local_infile=1; or use the Workbench import wizard)
DROP DATABASE IF EXISTS trendpulse;
CREATE DATABASE trendpulse;
USE trendpulse;

CREATE TABLE categories (
    category_id   INT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL
);

CREATE TABLE videos (
    video_id      VARCHAR(20) PRIMARY KEY,
    title         VARCHAR(255),
    channel_title VARCHAR(255),
    category_id   INT,
    publish_time  DATETIME,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE trending_records (
    record_id     INT PRIMARY KEY,
    video_id      VARCHAR(20) NOT NULL,
    country       CHAR(2) NOT NULL,
    trending_date DATE NOT NULL,
    views         BIGINT, likes BIGINT, dislikes BIGINT, comment_count BIGINT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

-- Loading (adjust paths; SET GLOBAL local_infile = 1; connect with OPT_LOCAL_INFILE=1)
LOAD DATA LOCAL INFILE 'data/categories_clean.csv' INTO TABLE categories
  FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;
LOAD DATA LOCAL INFILE 'data/videos_clean.csv' INTO TABLE videos
  FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;
LOAD DATA LOCAL INFILE 'data/trending_records_clean.csv' INTO TABLE trending_records
  FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;

SELECT 'categories' AS tbl, COUNT(*) AS n FROM categories
UNION ALL SELECT 'videos', COUNT(*) FROM videos
UNION ALL SELECT 'trending_records', COUNT(*) FROM trending_records;

-- Q1 SELECT/WHERE/ORDER BY/LIMIT/alias
SELECT video_id, views AS total_views, trending_date
FROM trending_records WHERE country = 'US' ORDER BY views DESC LIMIT 10;

-- Q2 DISTINCT
SELECT DISTINCT country FROM trending_records;

-- Q3 DISTINCT categories in use
SELECT DISTINCT c.category_name FROM categories c
INNER JOIN videos v ON v.category_id = c.category_id ORDER BY c.category_name;

-- Q4 GROUP BY + HAVING: categories with avg views above 1M
SELECT c.category_name, ROUND(AVG(t.views)) AS avg_views, COUNT(*) AS records
FROM trending_records t
JOIN videos v ON v.video_id = t.video_id
JOIN categories c ON c.category_id = v.category_id
GROUP BY c.category_name HAVING AVG(t.views) > 1000000 ORDER BY avg_views DESC;

-- Q5 channels with >= 5 distinct trending videos
SELECT channel_title, COUNT(DISTINCT video_id) AS n_videos
FROM videos GROUP BY channel_title HAVING COUNT(DISTINCT video_id) >= 5
ORDER BY n_videos DESC LIMIT 15;

-- Q6 INNER JOIN (3 tables): only records that have a video and category are wanted
SELECT t.country, t.trending_date, v.title, c.category_name, t.views
FROM trending_records t
INNER JOIN videos v ON v.video_id = t.video_id
INNER JOIN categories c ON c.category_id = v.category_id
ORDER BY t.views DESC LIMIT 10;

-- Q7 LEFT JOIN: keep every category, even ones with no videos (NULL = none)
SELECT c.category_id, c.category_name, COUNT(v.video_id) AS n_videos
FROM categories c LEFT JOIN videos v ON v.category_id = c.category_id
GROUP BY c.category_id, c.category_name HAVING COUNT(v.video_id) = 0;

-- Q8 RIGHT JOIN: keep every video, flag any without trending records
SELECT v.video_id, v.title, COUNT(t.record_id) AS n_records
FROM trending_records t RIGHT JOIN videos v ON v.video_id = t.video_id
GROUP BY v.video_id, v.title HAVING COUNT(t.record_id) = 0 LIMIT 10;

-- Cross-check values (compare with workbook Summary sheet)
SELECT COUNT(*) AS us_records FROM trending_records WHERE country = 'US';
SELECT ROUND(AVG(t.views)) AS avg_views_music
FROM trending_records t JOIN videos v ON v.video_id = t.video_id
JOIN categories c ON c.category_id = v.category_id WHERE c.category_name = 'Music';
