-- Add a creation date for new dossiers. Existing dossiers start their first
-- reminder countdown from the migration date because their original creation
-- dates were not stored by the application.

ALTER TABLE public.clients
ADD COLUMN IF NOT EXISTS date_creation timestamptz DEFAULT now();

UPDATE public.clients AS client
SET date_creation = now()
WHERE date_creation IS NULL;

ALTER TABLE public.clients
ALTER COLUMN date_creation SET DEFAULT now();

ALTER TABLE public.clients
ALTER COLUMN date_creation SET NOT NULL;
