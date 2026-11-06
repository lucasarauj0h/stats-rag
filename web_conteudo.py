"""Textos e exemplos da interface, separados do processamento das consultas."""

MODELO_GERACAO = "gemini-3.6-flash"

PERGUNTAS_SUGERIDAS = (
    "Why can the validation set approach produce unstable estimates of test error, and how does k-fold cross-validation address this limitation?",
    "How does the choice of k affect the bias, variance, and computational cost of cross-validation, particularly when comparing k-fold CV with LOOCV?",
    "How does the bootstrap estimate the uncertainty of a statistical estimator, and why does it sample observations with replacement?",
    "How do regression splines differ from polynomial regression, and how does the number and placement of knots influence model flexibility?",
    "How do generalized additive models extend linear models while preserving interpretability, and what limitations arise from their additive structure?",
    "How does a regression tree partition the predictor space and make predictions, and what are its main advantages and limitations compared with linear regression?",
    "Why does averaging multiple decision trees reduce variance, and how does random feature selection help random forests improve upon bagging?",
    "How does boosting differ from bagging in the way it constructs and combines trees, and how do the learning rate and number of trees influence its performance?",
)

EXEMPLOS = (
    {
        "id": "validacao_cruzada",
        "titulo": "Viés e variância: k-fold e LOOCV",
        "pergunta": "What is the bias–variance trade-off when choosing the number of folds in k-fold cross-validation, particularly compared with LOOCV?",
        "arquivo": "validacao_cruzada_kfold_loocv.pdf",
        "capitulo": 5,
        "slides": 3,
    },
    {
        "id": "splines",
        "titulo": "Splines e regressão polinomial: flexibilidade e nós",
        "pergunta": "How do regression splines differ from polynomial regression, and how does the choice of knots affect model flexibility and the risk of overfitting?",
        "arquivo": "splines_regressao_polinomial.pdf",
        "capitulo": 7,
        "slides": 5,
    },
    {
        "id": "random_forests",
        "titulo": "Random forests e bagging: árvores menos correlacionadas",
        "pergunta": "How do random forests reduce the correlation between trees compared with bagging, and why can this improve predictive performance?",
        "arquivo": "random_forests_bagging.pdf",
        "capitulo": 8,
        "slides": 5,
    },
)
