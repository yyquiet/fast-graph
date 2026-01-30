CREATE TABLE public.thread (
	thread_id varchar NOT NULL,
	created_at timestamp NOT NULL,
	updated_at timestamp NOT NULL,
	metadata jsonb NOT NULL,
	status varchar NOT NULL,
	CONSTRAINT thread_pkey PRIMARY KEY (thread_id)
);
CREATE INDEX thread_created_at_idx ON public.thread USING btree (created_at);
CREATE INDEX thread_metadata_idx ON public.thread USING gin (metadata jsonb_path_ops);
CREATE INDEX thread_status_idx ON public.thread USING btree (status, created_at);

CREATE TABLE public.checkpoints (
	thread_id text NOT NULL,
	checkpoint_ns text NOT NULL DEFAULT ''::text,
	checkpoint_id text NOT NULL,
	parent_checkpoint_id text NULL,
	"type" text NULL,
	"checkpoint" jsonb NOT NULL,
	metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
	CONSTRAINT checkpoints_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE INDEX checkpoints_thread_id_idx ON public.checkpoints USING btree (thread_id);

CREATE TABLE public.checkpoint_writes (
	thread_id text NOT NULL,
	checkpoint_ns text NOT NULL DEFAULT ''::text,
	checkpoint_id text NOT NULL,
	task_id text NOT NULL,
	idx int4 NOT NULL,
	channel text NOT NULL,
	"type" text NULL,
	"blob" bytea NOT NULL,
	task_path text NOT NULL DEFAULT ''::text,
	CONSTRAINT checkpoint_writes_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
CREATE INDEX checkpoint_writes_thread_id_idx ON public.checkpoint_writes USING btree (thread_id);

CREATE TABLE public.checkpoint_migrations (
	v int4 NOT NULL,
	CONSTRAINT checkpoint_migrations_pkey PRIMARY KEY (v)
);

CREATE TABLE public.checkpoint_blobs (
	thread_id text NOT NULL,
	checkpoint_ns text NOT NULL DEFAULT ''::text,
	channel text NOT NULL,
	"version" text NOT NULL,
	"type" text NOT NULL,
	"blob" bytea NULL,
	CONSTRAINT checkpoint_blobs_pkey PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);
CREATE INDEX checkpoint_blobs_thread_id_idx ON public.checkpoint_blobs USING btree (thread_id);

CREATE TABLE public.a2a_tasks (
	id varchar(36) NOT NULL,
	context_id varchar(36) NOT NULL,
	kind varchar(16) NOT NULL,
	status json NOT NULL,
	artifacts json NULL,
	history json NULL,
	metadata json NULL,
	CONSTRAINT a2a_tasks_pkey PRIMARY KEY (id)
);
CREATE INDEX ix_a2a_tasks_id ON public.a2a_tasks USING btree (id);
