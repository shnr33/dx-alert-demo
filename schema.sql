drop table if exists users;
create table users (
	id integer primary key autoincrement,
	uid integer,
    email text not null,
    alert_enabled integer
);