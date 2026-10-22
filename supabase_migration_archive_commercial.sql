-- Ajoute un indicateur d’archivage réversible aux suivis commerciaux.
-- Les dossiers existants restent actifs grâce à la valeur par défaut false.
ALTER TABLE public.rendez_vous_commerciaux
ADD COLUMN IF NOT EXISTS archive boolean NOT NULL DEFAULT false;
