# PL-lederfordeling – responsiv højde (0.52.7)

Fejlrettelsen sikrer, at `PLWiringDiagramWidget` aldrig tegner efter en kunstig 620 px minimumshøjde, når layoutet reelt har mindre plads. Geometrien bruger widgettens faktiske højde ned til 470 px og komprimerer kabelkort, luft og PL-dåse kontrolleret. Bundindføring 4-6 og hele lampeudtagets terminalpanel forbliver derfor synlige, mens dialogens OK/Annuller/Anvend-footer fortsat ligger fast uden for scrollområdet.
