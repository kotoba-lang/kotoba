-- HuggingFace Hub task popularity: dataset count per task category.
MODEL (
  name dev.mv_hfhub_task_popularity,
  kind FULL,
  dialect postgres,
  description 'Per task_category: dataset count from edge_hfhub_dataset_task.',
  grain [task_category],
  tags [hfhub, task, dataset, popularity]
);

SELECT
  task_category,
  COUNT(*) AS dataset_count
FROM edge_hfhub_dataset_task
GROUP BY task_category
