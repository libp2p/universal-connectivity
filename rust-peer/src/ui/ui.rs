/// the async UI trait
#[async_trait::async_trait]
pub trait Ui: Send {
    /// Run the UI
    async fn run(&mut self) -> anyhow::Result<()>;
}
